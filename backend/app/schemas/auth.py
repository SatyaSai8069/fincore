from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from app.models.user import KYCStatus, UserRole


class UserRegisterRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=150)
    phone_number: Optional[str] = Field(default=None, max_length=20)
    password: str = Field(..., min_length=8, max_length=128)
    kyc_document_ref: Optional[str] = Field(default=None, max_length=100)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)
    mfa_code: Optional[str] = Field(default=None, min_length=6, max_length=6)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int
    role: UserRole


class UserResponse(BaseModel):
    id: str
    customer_code: str
    email: EmailStr
    full_name: str
    phone_number: Optional[str]
    role: UserRole
    kyc_status: KYCStatus
    is_active: bool
    mfa_enabled: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MFASetupResponse(BaseModel):
    secret: str
    provisioning_uri: str


class MFAVerifyRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=6)