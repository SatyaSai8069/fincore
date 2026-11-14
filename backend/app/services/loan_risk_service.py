import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.ledger import BankAccount, JournalTransaction
from app.models.loan import InstallmentStatus, Loan, LoanInstallment, LoanStatus, LoanType
from app.models.risk import RiskAlert, RiskSeverity
from app.services.ledger_service import LedgerService, quantize_money

LOAN_ANNUAL_RATES: dict[LoanType, Decimal] = {
    LoanType.HOME: Decimal("0.0850"),
    LoanType.EDUCATION: Decimal("0.0925"),
    LoanType.BUSINESS: Decimal("0.1150"),
    LoanType.PERSONAL: Decimal("0.1300"),
}


def calculate_monthly_emi(
    principal: Decimal, annual_rate: Decimal, tenure_months: int
) -> Decimal:
    monthly_rate = float(annual_rate) / 12.0
    p = float(principal)
    n = tenure_months
    if monthly_rate == 0:
        return quantize_money(principal / Decimal(n))
    factor = (1.0 + monthly_rate) ** n
    emi = p * monthly_rate * factor / (factor - 1.0)
    return quantize_money(Decimal(str(emi)))


class LoanService:
    @classmethod
    async def originate_and_disburse_loan(
        cls,
        db: AsyncSession,
        user_id: str,
        account: BankAccount,
        loan_type: LoanType,
        principal_amount: Decimal,
        tenure_months: int,
        purpose: str | None = None,
    ) -> Loan:
        principal = quantize_money(principal_amount)
        annual_rate = LOAN_ANNUAL_RATES[loan_type]
        emi = calculate_monthly_emi(principal, annual_rate, tenure_months)
        loan_number = f"LN-{random.randint(10000000, 99999999)}"

        loan = Loan(
            loan_number=loan_number,
            user_id=user_id,
            disbursement_account_id=account.id,
            loan_type=loan_type,
            currency=account.currency,
            principal_amount=principal,
            annual_interest_rate=annual_rate,
            tenure_months=tenure_months,
            emi_amount=emi,
            outstanding_principal=principal,
            status=LoanStatus.ACTIVE,
            purpose=purpose,
        )
        db.add(loan)
        await db.flush()

        # Generate full reducing-balance amortization schedule
        remaining = principal
        monthly_rate = annual_rate / Decimal("12")
        now = datetime.now(timezone.utc)

        for idx in range(1, tenure_months + 1):
            interest_comp = quantize_money(remaining * monthly_rate)
            if idx == tenure_months:
                principal_comp = remaining
                installment_emi = quantize_money(principal_comp + interest_comp)
            else:
                principal_comp = quantize_money(emi - interest_comp)
                installment_emi = emi

            remaining = quantize_money(max(Decimal("0.0000"), remaining - principal_comp))
            installment = LoanInstallment(
                loan_id=loan.id,
                installment_number=idx,
                due_date=now + timedelta(days=30 * idx),
                emi_amount=installment_emi,
                principal_component=principal_comp,
                interest_component=interest_comp,
                remaining_balance=remaining,
                status=InstallmentStatus.PENDING,
            )
            db.add(installment)

        # Disburse loan principal into customer's bank account via double-entry ledger
        vault = await LedgerService.get_or_create_clearing_account(db, account.currency)
        await LedgerService.post_double_entry(
            db=db,
            debit_account=vault,
            credit_account=account,
            amount=principal,
            transaction_type="LOAN_DISBURSEMENT",
            description=f"Loan disbursement {loan_number} ({loan_type.value})",
            initiated_by_user_id=user_id,
        )
        await db.flush()
        return loan

    @staticmethod
    async def pay_next_emi(
        db: AsyncSession,
        loan: Loan,
        account: BankAccount,
        user_id: str,
    ) -> LoanInstallment:
        res = await db.execute(
            select(LoanInstallment)
            .where(
                LoanInstallment.loan_id == loan.id,
                LoanInstallment.status != InstallmentStatus.PAID,
            )
            .order_by(LoanInstallment.installment_number.asc())
        )
        installment = res.scalars().first()
        if not installment:
            raise ValueError("All installments for this loan are already paid")

        total_due = quantize_money(installment.emi_amount + installment.penalty_amount)
        vault = await LedgerService.get_or_create_clearing_account(db, account.currency)

        await LedgerService.post_double_entry(
            db=db,
            debit_account=account,
            credit_account=vault,
            amount=total_due,
            transaction_type="LOAN_EMI_PAYMENT",
            description=f"EMI #{installment.installment_number} for {loan.loan_number}",
            initiated_by_user_id=user_id,
        )

        installment.status = InstallmentStatus.PAID
        installment.paid_at = datetime.now(timezone.utc)
        loan.outstanding_principal = quantize_money(
            max(Decimal("0.0000"), loan.outstanding_principal - installment.principal_component)
        )
        if loan.outstanding_principal == Decimal("0.0000"):
            loan.status = LoanStatus.CLOSED

        await db.flush()
        return installment


class RiskEngineService:
    HIGH_VALUE_THRESHOLD = Decimal("250000.0000")
    VELOCITY_WINDOW_MINUTES = 10
    VELOCITY_MAX_TX = 5

    @classmethod
    async def evaluate_transaction(
        cls,
        db: AsyncSession,
        user_id: str,
        account_number: str,
        amount: Decimal,
        transaction_reference: str | None = None,
    ) -> RiskAlert:
        score = 10
        rules: list[str] = []

        if amount >= cls.HIGH_VALUE_THRESHOLD:
            score += 55
            rules.append("HIGH_VALUE_THRESHOLD_EXCEEDED")
        elif amount >= Decimal("50000.0000"):
            score += 25
            rules.append("ELEVATED_AMOUNT_MONITORING")

        window_start = datetime.now(timezone.utc) - timedelta(
            minutes=cls.VELOCITY_WINDOW_MINUTES
        )
        recent_count_res = await db.execute(
            select(func.count(JournalTransaction.id)).where(
                JournalTransaction.initiated_by_user_id == user_id,
                JournalTransaction.created_at >= window_start,
            )
        )
        recent_count = recent_count_res.scalar() or 0
        if recent_count >= cls.VELOCITY_MAX_TX:
            score += 35
            rules.append("HIGH_VELOCITY_BURST")

        score = min(100, score)
        if score >= 80:
            severity = RiskSeverity.CRITICAL
        elif score >= 60:
            severity = RiskSeverity.HIGH
        elif score >= 35:
            severity = RiskSeverity.MEDIUM
        else:
            severity = RiskSeverity.LOW

        triggered = ",".join(rules) if rules else "BASELINE_OK"
        alert = RiskAlert(
            user_id=user_id,
            account_number=account_number,
            transaction_reference=transaction_reference,
            risk_score=score,
            severity=severity,
            rule_triggered=triggered,
            amount=quantize_money(amount),
            details=f"Risk score {score}/100 ({severity.value}) | Rules: {triggered}",
        )
        db.add(alert)
        await db.flush()
        return alert