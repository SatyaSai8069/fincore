from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.db.session import get_db
from app.ml.financial_engine import FinancialIntelligenceEngine
from app.models.ledger import AccountType, BankAccount
from app.models.user import User, UserRole
from app.schemas.intelligence import (
    FinancialInsightsResponse,
    SavingsGoalPlanResponse,
    SavingsGoalRequest,
)

router = APIRouter(prefix="/intelligence", tags=["Financial Intelligence & AI"])


async def _get_accessible_account(
    db: AsyncSession, account_number: str, current_user: User
) -> BankAccount:
    res = await db.execute(
        select(BankAccount).where(BankAccount.account_number == account_number)
    )
    account = res.scalar_one_or_none()
    if not account or account.account_type == AccountType.SYSTEM_CLEARING:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Account not found"
        )
    if account.user_id != current_user.id and current_user.role not in (
        UserRole.ADMIN,
        UserRole.AUDITOR,
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return account


@router.get("/insights/{account_number}", response_model=FinancialInsightsResponse)
async def get_financial_insights(
    account_number: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    account = await _get_accessible_account(db, account_number, current_user)
    return await FinancialIntelligenceEngine.generate_account_insights(
        db=db,
        account=account,
        user_id=account.user_id or current_user.id,
    )


@router.post("/savings-goal", response_model=SavingsGoalPlanResponse)
async def plan_savings_goal(
    payload: SavingsGoalRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    account = await _get_accessible_account(db, payload.account_number, current_user)
    return FinancialIntelligenceEngine.compute_savings_goal_plan(
        account=account,
        goal_name=payload.goal_name,
        target_amount=payload.target_amount,
        months_to_goal=payload.months_to_goal,
    )