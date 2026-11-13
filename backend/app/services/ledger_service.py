import random
import uuid
from decimal import Decimal, ROUND_HALF_EVEN
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.ledger import (
    AccountStatus,
    AccountType,
    BankAccount,
    CurrencyCode,
    EntryDirection,
    JournalTransaction,
    LedgerEntry,
)

MONEY_QUANT = Decimal("0.0001")


def quantize_money(amount: Decimal) -> Decimal:
    return amount.quantize(MONEY_QUANT, rounding=ROUND_HALF_EVEN)


DEFAULT_INTEREST_RATES: dict[AccountType, Decimal] = {
    AccountType.SAVINGS: Decimal("0.0400"),
    AccountType.CURRENT: Decimal("0.0000"),
    AccountType.SALARY: Decimal("0.0150"),
    AccountType.SYSTEM_CLEARING: Decimal("0.0000"),
}


class LedgerService:
    @staticmethod
    async def get_or_create_clearing_account(
        db: AsyncSession, currency: CurrencyCode
    ) -> BankAccount:
        clearing_number = f"FIN-CLR-{currency.value}"
        result = await db.execute(
            select(BankAccount).where(BankAccount.account_number == clearing_number)
        )
        account = result.scalar_one_or_none()
        if account:
            return account

        account = BankAccount(
            account_number=clearing_number,
            user_id=None,
            account_type=AccountType.SYSTEM_CLEARING,
            currency=currency,
            status=AccountStatus.ACTIVE,
            interest_rate_annual=Decimal("0.0000"),
            available_balance=Decimal("999999999.0000"),
            ledger_balance=Decimal("999999999.0000"),
            nickname=f"FINORA Central Vault ({currency.value})",
        )
        db.add(account)
        await db.flush()
        return account

    @staticmethod
    async def post_double_entry(
        db: AsyncSession,
        debit_account: BankAccount,
        credit_account: BankAccount,
        amount: Decimal,
        transaction_type: str,
        description: str,
        initiated_by_user_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> JournalTransaction:
        amount = quantize_money(amount)
        if amount <= Decimal("0.0000"):
            raise ValueError("Transaction amount must be strictly positive")

        if debit_account.currency != credit_account.currency:
            raise ValueError("Cross-currency posting requires explicit FX conversion")

        if debit_account.id == credit_account.id:
            raise ValueError("Debit and credit accounts must be distinct")

        if debit_account.status != AccountStatus.ACTIVE:
            raise ValueError(f"Debit account {debit_account.account_number} is not active")

        if credit_account.status != AccountStatus.ACTIVE:
            raise ValueError(f"Credit account {credit_account.account_number} is not active")

        if debit_account.available_balance < amount:
            raise ValueError("Insufficient available balance")

        debit_account.available_balance = quantize_money(
            debit_account.available_balance - amount
        )
        debit_account.ledger_balance = quantize_money(
            debit_account.ledger_balance - amount
        )

        credit_account.available_balance = quantize_money(
            credit_account.available_balance + amount
        )
        credit_account.ledger_balance = quantize_money(
            credit_account.ledger_balance + amount
        )

        ref_num = f"TXN-{uuid.uuid4().hex[:12].upper()}"
        journal = JournalTransaction(
            reference_number=ref_num,
            idempotency_key=idempotency_key,
            transaction_type=transaction_type,
            currency=debit_account.currency,
            amount=amount,
            description=description,
            initiated_by_user_id=initiated_by_user_id,
        )
        db.add(journal)
        await db.flush()

        debit_line = LedgerEntry(
            journal_id=journal.id,
            account_id=debit_account.id,
            direction=EntryDirection.DEBIT,
            amount=amount,
            balance_after=debit_account.ledger_balance,
        )
        credit_line = LedgerEntry(
            journal_id=journal.id,
            account_id=credit_account.id,
            direction=EntryDirection.CREDIT,
            amount=amount,
            balance_after=credit_account.ledger_balance,
        )
        db.add_all([debit_line, credit_line])
        await db.flush()
        return journal

    @classmethod
    async def create_customer_account(
        cls,
        db: AsyncSession,
        user_id: str,
        account_type: AccountType,
        currency: CurrencyCode,
        nickname: str | None = None,
        initial_deposit: Decimal = Decimal("0.0000"),
    ) -> BankAccount:
        if account_type == AccountType.SYSTEM_CLEARING:
            raise ValueError("Customers cannot open system clearing accounts")

        account_number = f"FIN{random.randint(1000000000, 9999999999)}"
        account = BankAccount(
            account_number=account_number,
            user_id=user_id,
            account_type=account_type,
            currency=currency,
            status=AccountStatus.ACTIVE,
            interest_rate_annual=DEFAULT_INTEREST_RATES[account_type],
            available_balance=Decimal("0.0000"),
            ledger_balance=Decimal("0.0000"),
            nickname=nickname or f"{account_type.value.title()} Account",
        )
        db.add(account)
        await db.flush()

        initial_deposit = quantize_money(initial_deposit)
        if initial_deposit > Decimal("0.0000"):
            vault = await cls.get_or_create_clearing_account(db, currency)
            await cls.post_double_entry(
                db=db,
                debit_account=vault,
                credit_account=account,
                amount=initial_deposit,
                transaction_type="OPENING_DEPOSIT",
                description=f"Opening deposit for {account_number}",
                initiated_by_user_id=user_id,
            )

        return account