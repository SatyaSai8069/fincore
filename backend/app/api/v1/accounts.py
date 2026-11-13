from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user, require_roles
from app.api.v1.auth import record_audit
from app.db.session import get_db
from app.models.ledger import (
    AccountStatus,
    AccountType,
    BankAccount,
    LedgerEntry,
)
from app.models.user import User, UserRole
from app.schemas.account import (
    AccountCreateRequest,
    AccountResponse,
    AccountUpdateRequest,
    InterestProjectionResponse,
    LedgerEntryResponse,
)
from app.services.ledger_service import LedgerService, quantize_money

router = APIRouter(prefix="/accounts", tags=["Accounts & Ledger"])


@router.post("", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
async def create_account(
    payload: AccountCreateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        account = await LedgerService.create_customer_account(
            db=db,
            user_id=current_user.id,
            account_type=payload.account_type,
            currency=payload.currency,
            nickname=payload.nickname,
            initial_deposit=payload.initial_deposit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    await record_audit(
        db=db,
        action="ACCOUNT_CREATED",
        resource_type="bank_account",
        actor_user_id=current_user.id,
        resource_id=account.id,
        ip_address=request.client.host if request.client else None,
        details=f"Opened {account.account_type.value} ({account.currency.value}) {account.account_number}",
    )
    await db.commit()
    await db.refresh(account)
    return account


@router.get("", response_model=list[AccountResponse])
async def list_my_accounts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(BankAccount)
        .where(BankAccount.user_id == current_user.id)
        .order_by(BankAccount.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/admin/all", response_model=list[AccountResponse])
async def list_all_bank_accounts(
    _: User = Depends(require_roles(UserRole.ADMIN, UserRole.AUDITOR)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(BankAccount)
        .where(BankAccount.account_type != AccountType.SYSTEM_CLEARING)
        .order_by(BankAccount.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/{account_number}", response_model=AccountResponse)
async def get_account_details(
    account_number: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(BankAccount).where(BankAccount.account_number == account_number)
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    if account.user_id != current_user.id and current_user.role not in (
        UserRole.ADMIN,
        UserRole.AUDITOR,
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return account


@router.patch("/{account_number}", response_model=AccountResponse)
async def update_or_close_account(
    account_number: str,
    payload: AccountUpdateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(BankAccount).where(BankAccount.account_number == account_number)
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    if account.user_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    if payload.nickname is not None:
        account.nickname = payload.nickname.strip()

    if payload.status is not None:
        if payload.status == AccountStatus.CLOSED and account.ledger_balance != Decimal("0.0000"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Account balance must be zero before closing",
            )
        account.status = payload.status

    await record_audit(
        db=db,
        action="ACCOUNT_UPDATED",
        resource_type="bank_account",
        actor_user_id=current_user.id,
        resource_id=account.id,
        ip_address=request.client.host if request.client else None,
        details=f"Updated {account.account_number} status={account.status.value}",
    )
    await db.commit()
    await db.refresh(account)
    return account


@router.get("/{account_number}/interest-projection", response_model=InterestProjectionResponse)
async def get_interest_projection(
    account_number: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(BankAccount).where(BankAccount.account_number == account_number)
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    if account.user_id != current_user.id and current_user.role not in (
        UserRole.ADMIN,
        UserRole.AUDITOR,
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    annual_interest = quantize_money(account.ledger_balance * account.interest_rate_annual)
    monthly_interest = quantize_money(annual_interest / Decimal("12"))

    return InterestProjectionResponse(
        account_number=account.account_number,
        account_type=account.account_type,
        currency=account.currency,
        principal_balance=account.ledger_balance,
        annual_interest_rate=account.interest_rate_annual,
        projected_annual_interest=annual_interest,
        projected_monthly_interest=monthly_interest,
    )


@router.get("/{account_number}/ledger", response_model=list[LedgerEntryResponse])
async def get_account_ledger_entries(
    account_number: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(BankAccount).where(BankAccount.account_number == account_number)
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    if account.user_id != current_user.id and current_user.role not in (
        UserRole.ADMIN,
        UserRole.AUDITOR,
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    entries_res = await db.execute(
        select(LedgerEntry)
        .where(LedgerEntry.account_id == account.id)
        .order_by(LedgerEntry.created_at.desc())
    )
    return list(entries_res.scalars().all())