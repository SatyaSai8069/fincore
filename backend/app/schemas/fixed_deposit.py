from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field
from app.models.fixed_deposit import FDStatus
from app.models.ledger import CurrencyCode


class FDPlanInfo(BaseModel):
    plan_code: str
    plan_name: str
    tenure_months: int
    annual_interest_rate_percent: float
    min_amount: Decimal
    compounding: str


class FDCreateRequest(BaseModel):
    source_account_number: str = Field(..., min_length=6, max_length=20)
    plan_code: str = Field(..., min_length=2, max_length=32)
    principal_amount: Decimal = Field(..., gt=Decimal("999.99"), max_digits=19, decimal_places=4)


class FDResponse(BaseModel):
    id: str
    fd_number: str
    plan_name: str
    currency: CurrencyCode
    principal_amount: Decimal
    annual_interest_rate: Decimal
    tenure_months: int
    maturity_amount: Decimal
    interest_earned: Decimal
    status: FDStatus
    maturity_date: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)