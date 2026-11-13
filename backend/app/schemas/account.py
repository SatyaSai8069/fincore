from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.ledger import (
    AccountStatus,
    AccountType,
    CurrencyCode,
    EntryDirection,
)


class AccountCreateRequest(BaseModel):
    account_type: AccountType = AccountType.SAVINGS
    currency: CurrencyCode = CurrencyCode.INR
    nickname: Optional[str] = Field(default=None, max_length=80)
    initial_deposit: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"), max_digits=19, decimal_places=4)


class AccountUpdateRequest(BaseModel):
    nickname: Optional[str] = Field(default=None, max_length=80)
    status: Optional[AccountStatus] = None


class AccountResponse(BaseModel):
    id: str
    account_number: str
    user_id: Optional[str]
    account_type: AccountType
    currency: CurrencyCode
    status: AccountStatus
    interest_rate_annual: Decimal
    available_balance: Decimal
    ledger_balance: Decimal
    nickname: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InterestProjectionResponse(BaseModel):
    account_number: str
    account_type: AccountType
    currency: CurrencyCode
    principal_balance: Decimal
    annual_interest_rate: Decimal
    projected_annual_interest: Decimal
    projected_monthly_interest: Decimal


class LedgerEntryResponse(BaseModel):
    id: str
    journal_id: str
    account_id: str
    direction: EntryDirection
    amount: Decimal
    balance_after: Decimal
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)