import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.api.v1.auth import record_audit
from app.db.session import get_db
from app.models.fixed_deposit import FDStatus, FixedDeposit
from app.models.ledger import AccountType, BankAccount
from app.models.user import User
from app.schemas.fixed_deposit import FDCreateRequest, FDPlanInfo, FDResponse
from app.services.ledger_service import LedgerService, quantize_money

router = APIRouter(prefix="/fixed-deposits", tags=["Fixed Deposits & Term Plans"])

FD_PLANS: dict[str, dict] = {
    "SHORT_6M": {
        "plan_code": "SHORT_6M",
        "plan_name": "FINORA Flexi-6 Term Deposit",
        "tenure_months": 6,
        "annual_rate": Decimal("0.0675"),
        "min_amount": Decimal("5000.0000"),
        "compounding": "Quarterly",
    },
    "GROWTH_12M": {
        "plan_code": "GROWTH_12M",
        "plan_name": "FINORA Prime 1-Year Deposit",
        "tenure_months": 12,
        "annual_rate": Decimal("0.0750"),
        "min_amount": Decimal("10000.0000"),
        "compounding": "Quarterly",
    },
    "WEALTH_36M": {
        "plan_code": "WEALTH_36M",
        "plan_name": "FINORA Sovereign 3-Year Vault",
        "tenure_months": 36,
        "annual_rate": Decimal("0.0810"),
        "min_amount": Decimal("25000.0000"),
        "compounding": "Quarterly",
    },
    "ELITE_60M": {
        "plan_code": "ELITE_60M",
        "plan_name": "FINORA Platinum 5-Year Max Yield",
        "tenure_months": 60,
        "annual_rate": Decimal("0.0850"),
        "min_amount": Decimal("50000.0000"),
        "compounding": "Quarterly",
    },
}


def compute_quarterly_compound_maturity(
    principal: Decimal, annual_rate: Decimal, tenure_months: int
) -> tuple[Decimal, Decimal]:
    p = float(principal)
    r = float(annual_rate)
    years = tenure_months / 12.0
    maturity = p * ((1.0 + (r / 4.0)) ** (4.0 * years))
    maturity_dec = quantize_money(Decimal(str(maturity)))
    interest_dec = quantize_money(maturity_dec - principal)
    return maturity_dec, interest_dec


@router.get("/plans", response_model=list[FDPlanInfo])
async def list_fd_plans():
    return [
        FDPlanInfo(
            plan_code=p["plan_code"],
            plan_name=p["plan_name"],
            tenure_months=p["tenure_months"],
            annual_interest_rate_percent=round(float(p["annual_rate"]) * 100, 2),
            min_amount=p["min_amount"],
            compounding=p["compounding"],
        )
        for p in FD_PLANS.values()
    ]


@router.post("", response_model=FDResponse, status_code=status.HTTP_201_CREATED)
async def open_fixed_deposit(
    payload: FDCreateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    plan = FD_PLANS.get(payload.plan_code)
    if not plan:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid FD plan code")

    principal = quantize_money(payload.principal_amount)
    if principal < plan["min_amount"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Minimum deposit for {plan['plan_name']} is {plan['min_amount']}",
        )

    acc_res = await db.execute(
        select(BankAccount).where(BankAccount.account_number == payload.source_account_number)
    )
    account = acc_res.scalar_one_or_none()
    if not account or account.account_type == AccountType.SYSTEM_CLEARING:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source account not found")
    if account.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    try:
        vault = await LedgerService.get_or_create_clearing_account(db, account.currency)
        await LedgerService.post_double_entry(
            db=db,
            debit_account=account,
            credit_account=vault,
            amount=principal,
            transaction_type="FD_BOOKING",
            description=f"Booked {plan['plan_name']} ({plan['tenure_months']}m)",
            initiated_by_user_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    maturity_amt, interest_amt = compute_quarterly_compound_maturity(
        principal, plan["annual_rate"], plan["tenure_months"]
    )
    fd_number = f"FD-{random.randint(10000000, 99999999)}"
    fd = FixedDeposit(
        fd_number=fd_number,
        user_id=current_user.id,
        source_account_id=account.id,
        plan_name=plan["plan_name"],
        currency=account.currency,
        principal_amount=principal,
        annual_interest_rate=plan["annual_rate"],
        tenure_months=plan["tenure_months"],
        maturity_amount=maturity_amt,
        interest_earned=interest_amt,
        status=FDStatus.ACTIVE,
        maturity_date=datetime.now(timezone.utc) + timedelta(days=30 * plan["tenure_months"]),
    )
    db.add(fd)

    await record_audit(
        db=db,
        action="FD_OPENED",
        resource_type="fixed_deposit",
        actor_user_id=current_user.id,
        resource_id=fd_number,
        ip_address=request.client.host if request.client else None,
        details=f"Opened {fd_number} for {principal} {account.currency.value}",
    )
    await db.commit()
    await db.refresh(fd)
    return fd


@router.get("", response_model=list[FDResponse])
async def list_my_fixed_deposits(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(FixedDeposit)
        .where(FixedDeposit.user_id == current_user.id)
        .order_by(FixedDeposit.created_at.desc())
    )
    return list(res.scalars().all())


@router.post("/{fd_number}/liquidate", response_model=FDResponse)
async def liquidate_fixed_deposit(
    fd_number: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(FixedDeposit).where(FixedDeposit.fd_number == fd_number))
    fd = res.scalar_one_or_none()
    if not fd:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fixed deposit not found")
    if fd.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    if fd.status != FDStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="FD is already closed")

    acc_res = await db.execute(
        select(BankAccount).where(BankAccount.id == fd.source_account_id)
    )
    account = acc_res.scalar_one()

    # Premature closure credits principal + 50% of accrued projected yield
    payout = quantize_money(fd.principal_amount + (fd.interest_earned * Decimal("0.50")))
    vault = await LedgerService.get_or_create_clearing_account(db, account.currency)
    await LedgerService.post_double_entry(
        db=db,
        debit_account=vault,
        credit_account=account,
        amount=payout,
        transaction_type="FD_PAYOUT",
        description=f"FD Liquidation Payout {fd.fd_number}",
        initiated_by_user_id=current_user.id,
    )
    fd.status = FDStatus.CLOSED_PREMATURE
    await record_audit(
        db=db,
        action="FD_LIQUIDATED",
        resource_type="fixed_deposit",
        actor_user_id=current_user.id,
        resource_id=fd.fd_number,
        ip_address=request.client.host if request.client else None,
        details=f"Liquidated {fd.fd_number} with payout {payout}",
    )
    await db.commit()
    await db.refresh(fd)
    return fd