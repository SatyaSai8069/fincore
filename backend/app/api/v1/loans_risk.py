from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.api.deps import get_current_user, require_roles
from app.api.v1.auth import record_audit
from app.db.session import get_db
from app.models.ledger import AccountType, BankAccount
from app.models.loan import Loan
from app.models.risk import RiskAlert
from app.models.user import User, UserRole
from app.schemas.loan_risk import (
    LoanApplyRequest,
    LoanDetailResponse,
    LoanInstallmentResponse,
    LoanResponse,
    RiskAlertResponse,
    RiskEvaluateRequest,
)
from app.services.loan_risk_service import LoanService, RiskEngineService

router = APIRouter(tags=["Loans, EMI & Risk Intelligence"])


@router.post("/loans/apply", response_model=LoanDetailResponse, status_code=status.HTTP_201_CREATED)
async def apply_for_loan(
    payload: LoanApplyRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    acc_res = await db.execute(
        select(BankAccount).where(
            BankAccount.account_number == payload.disbursement_account_number
        )
    )
    account = acc_res.scalar_one_or_none()
    if not account or account.account_type == AccountType.SYSTEM_CLEARING:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Disbursement account not found"
        )
    if account.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied for account"
        )

    loan = await LoanService.originate_and_disburse_loan(
        db=db,
        user_id=current_user.id,
        account=account,
        loan_type=payload.loan_type,
        principal_amount=payload.principal_amount,
        tenure_months=payload.tenure_months,
        purpose=payload.purpose,
    )

    await record_audit(
        db=db,
        action="LOAN_DISBURSED",
        resource_type="loan",
        actor_user_id=current_user.id,
        resource_id=loan.loan_number,
        ip_address=request.client.host if request.client else None,
        details=f"Disbursed {loan.principal_amount} {loan.currency.value} ({loan.loan_number})",
    )
    await db.commit()

    full_res = await db.execute(
        select(Loan)
        .options(selectinload(Loan.installments))
        .where(Loan.id == loan.id)
    )
    return full_res.scalar_one()


@router.get("/loans", response_model=list[LoanResponse])
async def list_my_loans(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(Loan)
        .where(Loan.user_id == current_user.id)
        .order_by(Loan.created_at.desc())
    )
    return list(res.scalars().all())


@router.get("/loans/{loan_number}", response_model=LoanDetailResponse)
async def get_loan_schedule(
    loan_number: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(Loan)
        .options(selectinload(Loan.installments))
        .where(Loan.loan_number == loan_number)
    )
    loan = res.scalar_one_or_none()
    if not loan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loan not found")
    if loan.user_id != current_user.id and current_user.role not in (
        UserRole.ADMIN,
        UserRole.AUDITOR,
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return loan


@router.post("/loans/{loan_number}/pay-emi", response_model=LoanInstallmentResponse)
async def pay_loan_emi(
    loan_number: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    loan_res = await db.execute(select(Loan).where(Loan.loan_number == loan_number))
    loan = loan_res.scalar_one_or_none()
    if not loan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loan not found")
    if loan.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    acc_res = await db.execute(
        select(BankAccount).where(BankAccount.id == loan.disbursement_account_id)
    )
    account = acc_res.scalar_one()

    try:
        installment = await LoanService.pay_next_emi(
            db=db, loan=loan, account=account, user_id=current_user.id
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    await record_audit(
        db=db,
        action="LOAN_EMI_PAID",
        resource_type="loan",
        actor_user_id=current_user.id,
        resource_id=loan.loan_number,
        ip_address=request.client.host if request.client else None,
        details=f"Paid EMI #{installment.installment_number} ({installment.emi_amount})",
    )
    await db.commit()
    await db.refresh(installment)
    return installment


@router.post("/risk/evaluate", response_model=RiskAlertResponse, status_code=status.HTTP_201_CREATED)
async def evaluate_transaction_risk(
    payload: RiskEvaluateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    alert = await RiskEngineService.evaluate_transaction(
        db=db,
        user_id=current_user.id,
        account_number=payload.account_number,
        amount=payload.amount,
        transaction_reference=payload.transaction_reference,
    )
    await db.commit()
    await db.refresh(alert)
    return alert


@router.get("/risk/alerts", response_model=list[RiskAlertResponse])
async def list_risk_alerts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(RiskAlert).order_by(RiskAlert.created_at.desc())
    if current_user.role not in (UserRole.ADMIN, UserRole.AUDITOR):
        query = query.where(RiskAlert.user_id == current_user.id)
    res = await db.execute(query)
    return list(res.scalars().all())


@router.patch("/risk/alerts/{alert_id}/resolve", response_model=RiskAlertResponse)
async def resolve_risk_alert(
    alert_id: str,
    _: User = Depends(require_roles(UserRole.ADMIN, UserRole.AUDITOR)),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(RiskAlert).where(RiskAlert.id == alert_id))
    alert = res.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    alert.is_resolved = True
    await db.commit()
    await db.refresh(alert)
    return alert