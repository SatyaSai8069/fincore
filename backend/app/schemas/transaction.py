from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.ledger import CurrencyCode, EntryDirection


class DepositWithdrawRequest(BaseModel):
    account_number: str = Field(..., min_length=6, max_length=20)
    amount: Decimal = Field(..., gt=Decimal("0.00"), max_digits=19, decimal_places=4)
    description: Optional[str] = Field(default=None, max_length=255)
    idempotency_key: Optional[str] = Field(default=None, max_length=128)


class TransferRequest(BaseModel):
    from_account_number: str = Field(..., min_length=6, max_length=20)
    to_account_number: str = Field(..., min_length=6, max_length=20)
    amount: Decimal = Field(..., gt=Decimal("0.00"), max_digits=19, decimal_places=4)
    description: Optional[str] = Field(default=None, max_length=255)
    idempotency_key: Optional[str] = Field(default=None, max_length=128)


class TransactionReceiptResponse(BaseModel):
    reference_number: str
    transaction_type: str
    currency: CurrencyCode
    amount: Decimal
    converted_amount: Optional[Decimal] = None
    target_currency: Optional[CurrencyCode] = None
    fx_rate_applied: Optional[Decimal] = None
    description: Optional[str]
    from_account_number: Optional[str] = None
    to_account_number: Optional[str] = None
    source_available_balance: Optional[Decimal] = None
    target_available_balance: Optional[Decimal] = None
    created_at: datetime


class StatementItemResponse(BaseModel):
    entry_id: str
    reference_number: str
    transaction_type: str
    direction: EntryDirection
    amount: Decimal
    balance_after: Decimal
    description: Optional[str]
    created_at: datetime


class AccountStatementResponse(BaseModel):
    account_number: str
    currency: CurrencyCode
    current_available_balance: Decimal
    current_ledger_balance: Decimal
    total_credits: Decimal
    total_debits: Decimal
    items: list[StatementItemResponse]


class BeneficiaryCreateRequest(BaseModel):
    beneficiary_account_number: str = Field(..., min_length=6, max_length=20)
    nickname: Optional[str] = Field(default=None, max_length=80)
    daily_transfer_limit: Decimal = Field(
        default=Decimal("100000.0000"),
        gt=Decimal("0.00"),
        max_digits=19,
        decimal_places=4,
    )


class BeneficiaryResponse(BaseModel):
    id: str
    beneficiary_account_number: str
    beneficiary_name: str
    nickname: Optional[str]
    daily_transfer_limit: Decimal
    is_verified: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)