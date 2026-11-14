from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import require_roles
from app.api.v1.auth import record_audit
from app.db.session import get_db
from app.models.ledger import (
    AccountStatus,
    AccountType,
    BankAccount,
    CurrencyCode,
    EntryDirection,
    JournalTransaction,
    LedgerEntry,
)
from app.models.loan import Loan, LoanStatus
from app.models.risk import RiskAlert
from app.models.user import AuditLog, KYCStatus, User, UserRole

router = APIRouter(prefix="/admin", tags=["Admin & Compliance Governance"])


class PlatformOverviewResponse(BaseModel):
    total_customers: int
    active_bank_accounts: int
    total_journal_transactions: int
    active_loans_count: int
    unresolved_risk_alerts: int
    total_customer_deposits_by_currency: dict[str, Decimal]
    double_entry_balanced: bool


class AuditLogResponse(BaseModel):
    id: str
    actor_user_id: str | None
    action: str
    resource_type: str
    resource_id: str | None
    ip_address: str | None
    details: str | None
    created_at: str


class AccountStatusUpdateRequest(BaseModel):
    status: AccountStatus
    reason: str | None = None


class KYCUpdateRequest(BaseModel):
    kyc_status: KYCStatus


@router.get("/overview", response_model=PlatformOverviewResponse)
async def get_platform_overview(
    _: User = Depends(require_roles(UserRole.ADMIN, UserRole.AUDITOR)),
    db: AsyncSession = Depends(get_db),
):
    customers = (
        await db.execute(select(func.count(User.id)).where(User.role == UserRole.CUSTOMER))
    ).scalar() or 0

    accounts = (
        await db.execute(
            select(func.count(BankAccount.id)).where(
                BankAccount.account_type != AccountType.SYSTEM_CLEARING,
                BankAccount.status == AccountStatus.ACTIVE,
            )
        )
    ).scalar() or 0

    tx_count = (await db.execute(select(func.count(JournalTransaction.id)))).scalar() or 0

    active_loans = (
        await db.execute(select(func.count(Loan.id)).where(Loan.status == LoanStatus.ACTIVE))
    ).scalar() or 0

    unresolved_alerts = (
        await db.execute(
            select(func.count(RiskAlert.id)).where(RiskAlert.is_resolved.is_(False))
        )
    ).scalar() or 0

    deposits_by_curr: dict[str, Decimal] = {}
    for curr in CurrencyCode:
        total_bal = (
            await db.execute(
                select(func.coalesce(func.sum(BankAccount.available_balance), 0)).where(
                    BankAccount.currency == curr,
                    BankAccount.account_type != AccountType.SYSTEM_CLEARING,
                )
            )
        ).scalar()
        deposits_by_curr[curr.value] = Decimal(str(total_bal)).quantize(Decimal("0.0000"))

    # Verify global double-entry invariant: sum(DEBIT) == sum(CREDIT)
    debit_sum = (
        await db.execute(
            select(func.coalesce(func.sum(LedgerEntry.amount), 0)).where(
                LedgerEntry.direction == EntryDirection.DEBIT
            )
        )
    ).scalar()
    credit_sum = (
        await db.execute(
            select(func.coalesce(func.sum(LedgerEntry.amount), 0)).where(
                LedgerEntry.direction == EntryDirection.CREDIT
            )
        )
    ).scalar()
    is_balanced = Decimal(str(debit_sum)).quantize(Decimal("0.0000")) == Decimal(
        str(credit_sum)
    ).quantize(Decimal("0.0000"))

    return PlatformOverviewResponse(
        total_customers=customers,
        active_bank_accounts=accounts,
        total_journal_transactions=tx_count,
        active_loans_count=active_loans,
        unresolved_risk_alerts=unresolved_alerts,
        total_customer_deposits_by_currency=deposits_by_curr,
        double_entry_balanced=is_balanced,
    )


@router.get("/audit-logs", response_model=list[AuditLogResponse])
async def get_audit_logs(
    limit: int = 50,
    _: User = Depends(require_roles(UserRole.ADMIN, UserRole.AUDITOR)),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(AuditLog).order_by(AuditLog.created_at.desc()).limit(min(limit, 200))
    )
    logs = res.scalars().all()
    return [
        AuditLogResponse(
            id=item.id,
            actor_user_id=item.actor_user_id,
            action=item.action,
            resource_type=item.resource_type,
            resource_id=item.resource_id,
            ip_address=item.ip_address,
            details=item.details,
            created_at=item.created_at.isoformat(),
        )
        for item in logs
    ]


@router.patch("/accounts/{account_number}/status")
async def update_account_status(
    account_number: str,
    payload: AccountStatusUpdateRequest,
    request: Request,
    admin_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(BankAccount).where(BankAccount.account_number == account_number)
    )
    account = res.scalar_one_or_none()
    if not account or account.account_type == AccountType.SYSTEM_CLEARING:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    account.status = payload.status
    await record_audit(
        db=db,
        action=f"ACCOUNT_STATUS_{payload.status.value}",
        resource_type="bank_account",
        actor_user_id=admin_user.id,
        resource_id=account.account_number,
        ip_address=request.client.host if request.client else None,
        details=payload.reason or f"Status updated to {payload.status.value}",
    )
    await db.commit()
    return {"account_number": account.account_number, "status": account.status.value}


@router.patch("/users/{user_id}/kyc")
async def update_user_kyc(
    user_id: str,
    payload: KYCUpdateRequest,
    request: Request,
    admin_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(User).where(User.id == user_id))
    target = res.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    target.kyc_status = payload.kyc_status
    await record_audit(
        db=db,
        action=f"KYC_{payload.kyc_status.value}",
        resource_type="user",
        actor_user_id=admin_user.id,
        resource_id=target.id,
        ip_address=request.client.host if request.client else None,
        details=f"KYC updated to {payload.kyc_status.value} for {target.email}",
    )
    await db.commit()
    return {"user_id": target.id, "email": target.email, "kyc_status": target.kyc_status.value}