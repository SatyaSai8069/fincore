from decimal import Decimal
from pydantic import BaseModel, Field
from app.models.ledger import CurrencyCode


class CategoryBreakdownItem(BaseModel):
    category: str
    transaction_count: int
    total_amount: Decimal
    share_percent: float


class CashFlowPoint(BaseModel):
    day_offset: int
    date_label: str
    projected_balance: Decimal


class FinancialInsightsResponse(BaseModel):
    account_number: str
    currency: CurrencyCode
    current_balance: Decimal
    total_inflow: Decimal
    total_outflow: Decimal
    net_cash_flow: Decimal
    savings_rate_percent: float
    financial_health_score: int
    health_grade: str
    spending_by_category: list[CategoryBreakdownItem]
    thirty_day_forecast: list[CashFlowPoint]
    recommendations: list[str]


class SavingsGoalRequest(BaseModel):
    account_number: str = Field(..., min_length=6, max_length=20)
    goal_name: str = Field(..., min_length=2, max_length=100)
    target_amount: Decimal = Field(..., gt=Decimal("0.00"), max_digits=19, decimal_places=4)
    months_to_goal: int = Field(..., ge=1, le=240)


class SavingsGoalPlanResponse(BaseModel):
    goal_name: str
    currency: CurrencyCode
    current_account_balance: Decimal
    target_amount: Decimal
    shortfall_amount: Decimal
    months_to_goal: int
    required_monthly_contribution: Decimal
    expected_annual_yield_percent: float
    projected_interest_earned: Decimal
    feasibility_status: str