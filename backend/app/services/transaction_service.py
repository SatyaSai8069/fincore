from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.ledger import (
    BankAccount,
    CurrencyCode,
    EntryDirection,
    JournalTransaction,
    LedgerEntry,
)
from app.schemas.transaction import (
    AccountStatementResponse,
    StatementItemResponse,
    TransactionReceiptResponse,
)
from app.services.ledger_service import LedgerService, quantize_money

# Reference FX rates relative to 1 INR
RATES_PER_INR: dict[CurrencyCode, Decimal] = {
    CurrencyCode.INR: Decimal("1.000000"),
    CurrencyCode.USD: Decimal("0.011905"),  # ~84 INR per USD
    CurrencyCode.EUR: Decimal("0.010989"),  # ~91 INR per EUR
    CurrencyCode.GBP: Decimal("0.009346"),  # ~107 INR per GBP
}


def compute_fx_rate(source: CurrencyCode, target: CurrencyCode) -> Decimal:
    if source == target:
        return Decimal("1.000000")
    source_in_inr = Decimal("1.000000") / RATES_PER_INR[source]
    rate = source_in_inr * RATES_PER_INR[target]
    return rate.quantize(Decimal("0.000001"))


class TransactionService:
    @staticmethod
    async def _find_by_idempotency(
        db: AsyncSession, idempotency_key: str | None
    ) -> JournalTransaction | None:
        if not idempotency_key:
            return None
        res = await db.execute(
            select(JournalTransaction).where(
                JournalTransaction.idempotency_key == idempotency_key
            )
        )
        return res.scalar_one_or_none()

    @classmethod
    async def deposit(
        cls,
        db: AsyncSession,
        account: BankAccount,
        amount: Decimal,
        user_id: str,
        description: str | None = None,
        idempotency_key: str | None = None,
    ) -> TransactionReceiptResponse:
        existing = await cls._find_by_idempotency(db, idempotency_key)
        if existing:
            return TransactionReceiptResponse(
                reference_number=existing.reference_number,
                transaction_type=existing.transaction_type,
                currency=existing.currency,
                amount=existing.amount,
                description=existing.description,
                to_account_number=account.account_number,
                target_available_balance=account.available_balance,
                created_at=existing.created_at,
            )

        vault = await LedgerService.get_or_create_clearing_account(db, account.currency)
        journal = await LedgerService.post_double_entry(
            db=db,
            debit_account=vault,
            credit_account=account,
            amount=amount,
            transaction_type="CASH_DEPOSIT",
            description=description or f"Deposit to {account.account_number}",
            initiated_by_user_id=user_id,
            idempotency_key=idempotency_key,
        )
        return TransactionReceiptResponse(
            reference_number=journal.reference_number,
            transaction_type=journal.transaction_type,
            currency=account.currency,
            amount=journal.amount,
            description=journal.description,
            to_account_number=account.account_number,
            target_available_balance=account.available_balance,
            created_at=journal.created_at,
        )

    @classmethod
    async def withdraw(
        cls,
        db: AsyncSession,
        account: BankAccount,
        amount: Decimal,
        user_id: str,
        description: str | None = None,
        idempotency_key: str | None = None,
    ) -> TransactionReceiptResponse:
        existing = await cls._find_by_idempotency(db, idempotency_key)
        if existing:
            return TransactionReceiptResponse(
                reference_number=existing.reference_number,
                transaction_type=existing.transaction_type,
                currency=existing.currency,
                amount=existing.amount,
                description=existing.description,
                from_account_number=account.account_number,
                source_available_balance=account.available_balance,
                created_at=existing.created_at,
            )

        vault = await LedgerService.get_or_create_clearing_account(db, account.currency)
        journal = await LedgerService.post_double_entry(
            db=db,
            debit_account=account,
            credit_account=vault,
            amount=amount,
            transaction_type="CASH_WITHDRAWAL",
            description=description or f"Withdrawal from {account.account_number}",
            initiated_by_user_id=user_id,
            idempotency_key=idempotency_key,
        )
        return TransactionReceiptResponse(
            reference_number=journal.reference_number,
            transaction_type=journal.transaction_type,
            currency=account.currency,
            amount=journal.amount,
            description=journal.description,
            from_account_number=account.account_number,
            source_available_balance=account.available_balance,
            created_at=journal.created_at,
        )

    @classmethod
    async def transfer(
        cls,
        db: AsyncSession,
        source_account: BankAccount,
        target_account: BankAccount,
        amount: Decimal,
        user_id: str,
        description: str | None = None,
        idempotency_key: str | None = None,
    ) -> TransactionReceiptResponse:
        existing = await cls._find_by_idempotency(db, idempotency_key)
        if existing:
            return TransactionReceiptResponse(
                reference_number=existing.reference_number,
                transaction_type=existing.transaction_type,
                currency=existing.currency,
                amount=existing.amount,
                description=existing.description,
                from_account_number=source_account.account_number,
                to_account_number=target_account.account_number,
                source_available_balance=source_account.available_balance,
                target_available_balance=target_account.available_balance,
                created_at=existing.created_at,
            )

        amount = quantize_money(amount)

        # Same-currency atomic double-entry transfer
        if source_account.currency == target_account.currency:
            journal = await LedgerService.post_double_entry(
                db=db,
                debit_account=source_account,
                credit_account=target_account,
                amount=amount,
                transaction_type="INTERNAL_TRANSFER",
                description=description
                or f"Transfer {source_account.account_number} -> {target_account.account_number}",
                initiated_by_user_id=user_id,
                idempotency_key=idempotency_key,
            )
            return TransactionReceiptResponse(
                reference_number=journal.reference_number,
                transaction_type=journal.transaction_type,
                currency=source_account.currency,
                amount=journal.amount,
                converted_amount=journal.amount,
                target_currency=target_account.currency,
                fx_rate_applied=Decimal("1.000000"),
                description=journal.description,
                from_account_number=source_account.account_number,
                to_account_number=target_account.account_number,
                source_available_balance=source_account.available_balance,
                target_available_balance=target_account.available_balance,
                created_at=journal.created_at,
            )

        # Cross-currency transfer via FX clearing vaults (2 balanced double-entry journals)
        fx_rate = compute_fx_rate(source_account.currency, target_account.currency)
        converted_amount = quantize_money(amount * fx_rate)

        source_vault = await LedgerService.get_or_create_clearing_account(
            db, source_account.currency
        )
        target_vault = await LedgerService.get_or_create_clearing_account(
            db, target_account.currency
        )

        debit_journal = await LedgerService.post_double_entry(
            db=db,
            debit_account=source_account,
            credit_account=source_vault,
            amount=amount,
            transaction_type="FX_TRANSFER_OUT",
            description=description
            or f"FX Transfer {source_account.currency.value}->{target_account.currency.value} @ {fx_rate}",
            initiated_by_user_id=user_id,
            idempotency_key=idempotency_key,
        )

        await LedgerService.post_double_entry(
            db=db,
            debit_account=target_vault,
            credit_account=target_account,
            amount=converted_amount,
            transaction_type="FX_TRANSFER_IN",
            description=f"FX Settlement ref {debit_journal.reference_number} @ {fx_rate}",
            initiated_by_user_id=user_id,
        )

        return TransactionReceiptResponse(
            reference_number=debit_journal.reference_number,
            transaction_type="FX_TRANSFER",
            currency=source_account.currency,
            amount=amount,
            converted_amount=converted_amount,
            target_currency=target_account.currency,
            fx_rate_applied=fx_rate,
            description=debit_journal.description,
            from_account_number=source_account.account_number,
            to_account_number=target_account.account_number,
            source_available_balance=source_account.available_balance,
            target_available_balance=target_account.available_balance,
            created_at=debit_journal.created_at,
        )

    @staticmethod
    async def build_statement(
        db: AsyncSession, account: BankAccount
    ) -> AccountStatementResponse:
        stmt = (
            select(LedgerEntry, JournalTransaction)
            .join(JournalTransaction, LedgerEntry.journal_id == JournalTransaction.id)
            .where(LedgerEntry.account_id == account.id)
            .order_by(LedgerEntry.created_at.desc())
        )
        rows = (await db.execute(stmt)).all()

        total_credits = Decimal("0.0000")
        total_debits = Decimal("0.0000")
        items: list[StatementItemResponse] = []

        for entry, journal in rows:
            if entry.direction == EntryDirection.CREDIT:
                total_credits += entry.amount
            else:
                total_debits += entry.amount

            items.append(
                StatementItemResponse(
                    entry_id=entry.id,
                    reference_number=journal.reference_number,
                    transaction_type=journal.transaction_type,
                    direction=entry.direction,
                    amount=entry.amount,
                    balance_after=entry.balance_after,
                    description=journal.description,
                    created_at=entry.created_at,
                )
            )

        return AccountStatementResponse(
            account_number=account.account_number,
            currency=account.currency,
            current_available_balance=account.available_balance,
            current_ledger_balance=account.ledger_balance,
            total_credits=quantize_money(total_credits),
            total_debits=quantize_money(total_debits),
            items=items,
        )