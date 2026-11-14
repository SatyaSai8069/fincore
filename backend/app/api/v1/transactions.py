from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.api.v1.auth import record_audit
from app.db.session import get_db
from app.models.beneficiary import Beneficiary
from app.models.ledger import AccountType, BankAccount
from app.models.user import User, UserRole
from app.schemas.transaction import (
    AccountStatementResponse,
    BeneficiaryCreateRequest,
    BeneficiaryResponse,
    DepositWithdrawRequest,
    TransactionReceiptResponse,
    TransferRequest,
)
from app.services.transaction_service import TransactionService

router = APIRouter(prefix="/transactions", tags=["Transactions & Beneficiaries"])


async def _get_owned_account(
    db: AsyncSession, account_number: str, current_user: User
) -> BankAccount:
    res = await db.execute(
        select(BankAccount).where(BankAccount.account_number == account_number)
    )
    account = res.scalar_one_or_none()
    if not account or account.account_type == AccountType.SYSTEM_CLEARING:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Bank account not found"
        )
    if account.user_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied for this account"
        )
    return account


@router.post("/deposit", response_model=TransactionReceiptResponse, status_code=status.HTTP_201_CREATED)
async def deposit_funds(
    payload: DepositWithdrawRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    account = await _get_owned_account(db, payload.account_number, current_user)
    try:
        receipt = await TransactionService.deposit(
            db=db,
            account=account,
            amount=payload.amount,
            user_id=current_user.id,
            description=payload.description,
            idempotency_key=payload.idempotency_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    await record_audit(
        db=db,
        action="DEPOSIT_POSTED",
        resource_type="journal_transaction",
        actor_user_id=current_user.id,
        resource_id=receipt.reference_number,
        ip_address=request.client.host if request.client else None,
        details=f"Deposited {receipt.amount} {receipt.currency.value} to {account.account_number}",
    )
    await db.commit()
    return receipt


@router.post("/withdraw", response_model=TransactionReceiptResponse, status_code=status.HTTP_201_CREATED)
async def withdraw_funds(
    payload: DepositWithdrawRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    account = await _get_owned_account(db, payload.account_number, current_user)
    try:
        receipt = await TransactionService.withdraw(
            db=db,
            account=account,
            amount=payload.amount,
            user_id=current_user.id,
            description=payload.description,
            idempotency_key=payload.idempotency_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    await record_audit(
        db=db,
        action="WITHDRAWAL_POSTED",
        resource_type="journal_transaction",
        actor_user_id=current_user.id,
        resource_id=receipt.reference_number,
        ip_address=request.client.host if request.client else None,
        details=f"Withdrew {receipt.amount} {receipt.currency.value} from {account.account_number}",
    )
    await db.commit()
    return receipt


@router.post("/transfer", response_model=TransactionReceiptResponse, status_code=status.HTTP_201_CREATED)
async def transfer_funds(
    payload: TransferRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    source_account = await _get_owned_account(
        db, payload.from_account_number, current_user
    )

    target_res = await db.execute(
        select(BankAccount).where(
            BankAccount.account_number == payload.to_account_number
        )
    )
    target_account = target_res.scalar_one_or_none()
    if not target_account or target_account.account_type == AccountType.SYSTEM_CLEARING:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Destination account not found",
        )

    try:
        receipt = await TransactionService.transfer(
            db=db,
            source_account=source_account,
            target_account=target_account,
            amount=payload.amount,
            user_id=current_user.id,
            description=payload.description,
            idempotency_key=payload.idempotency_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    await record_audit(
        db=db,
        action="TRANSFER_POSTED",
        resource_type="journal_transaction",
        actor_user_id=current_user.id,
        resource_id=receipt.reference_number,
        ip_address=request.client.host if request.client else None,
        details=(
            f"Transfer {receipt.amount} {receipt.currency.value} "
            f"{source_account.account_number} -> {target_account.account_number}"
        ),
    )
    await db.commit()
    return receipt


@router.get("/statement/{account_number}", response_model=AccountStatementResponse)
async def get_account_statement(
    account_number: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    account = await _get_owned_account(db, account_number, current_user)
    return await TransactionService.build_statement(db, account)


@router.post("/beneficiaries", response_model=BeneficiaryResponse, status_code=status.HTTP_201_CREATED)
async def add_beneficiary(
    payload: BeneficiaryCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    acc_res = await db.execute(
        select(BankAccount).where(
            BankAccount.account_number == payload.beneficiary_account_number
        )
    )
    target_acc = acc_res.scalar_one_or_none()
    if not target_acc or target_acc.account_type == AccountType.SYSTEM_CLEARING:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Beneficiary bank account not found",
        )
    if target_acc.user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot add your own account as an external beneficiary",
        )

    owner_res = await db.execute(select(User).where(User.id == target_acc.user_id))
    owner = owner_res.scalar_one_or_none()

    existing_res = await db.execute(
        select(Beneficiary).where(
            Beneficiary.owner_user_id == current_user.id,
            Beneficiary.beneficiary_account_number == payload.beneficiary_account_number,
        )
    )
    if existing_res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Beneficiary already registered",
        )

    beneficiary = Beneficiary(
        owner_user_id=current_user.id,
        beneficiary_account_number=target_acc.account_number,
        beneficiary_name=owner.full_name if owner else "FINORA Account Holder",
        nickname=payload.nickname,
        daily_transfer_limit=payload.daily_transfer_limit,
    )
    db.add(beneficiary)
    await db.commit()
    await db.refresh(beneficiary)
    return beneficiary


@router.get("/beneficiaries", response_model=list[BeneficiaryResponse])
async def list_beneficiaries(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(Beneficiary)
        .where(Beneficiary.owner_user_id == current_user.id)
        .order_by(Beneficiary.created_at.desc())
    )
    return list(res.scalars().all())