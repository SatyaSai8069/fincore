from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.ledger import CurrencyCode
from app.models.loan import InstallmentStatus, LoanStatus, LoanType
from app.models.risk import RiskSeverity


class LoanApplyRequest(BaseModel):
    disbursement_account_number: str = Field(..., min_length=6, max_length=20)
    loan_type: LoanType = LoanType.PERSONAL
    principal_amount: Decimal = Field(..., gt=Decimal("1000.00"), max_digits=19, decimal_places=4)
    tenure_months: int = Field(..., ge=3, le=360)
    purpose: Optional[str] = Field(default=None, max_length=255)


class LoanInstallmentResponse(BaseModel):
    id: str
    installment_number: int
    due_date: datetime
    emi_amount: Decimal
    principal_component: Decimal
    interest_component: Decimal
    penalty_amount: Decimal
    remaining_balance: Decimal
    status: InstallmentStatus
    paid_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class LoanResponse(BaseModel):
    id: str
    loan_number: str
    loan_type: LoanType
    currency: CurrencyCode
    principal_amount: Decimal
    annual_interest_rate: Decimal
    tenure_months: int
    emi_amount: Decimal
    outstanding_principal: Decimal
    status: LoanStatus
    purpose: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LoanDetailResponse(LoanResponse):
    installments: list[LoanInstallmentResponse]


class RiskEvaluateRequest(BaseModel):
    account_number: str = Field(..., min_length=6, max_length=20)
    amount: Decimal = Field(..., gt=Decimal("0.00"), max_digits=19, decimal_places=4)
    transaction_reference: Optional[str] = None


class RiskAlertResponse(BaseModel):
    id: str
    user_id: str
    account_number: str
    transaction_reference: Optional[str]
    risk_score: int
    severity: RiskSeverity
    rule_triggered: str
    amount: Decimal
    details: str
    is_resolved: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)