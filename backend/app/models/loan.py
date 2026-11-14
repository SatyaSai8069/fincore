import uuid
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum as PyEnum
from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.session import Base
from app.models.ledger import CurrencyCode


class LoanType(str, PyEnum):
    PERSONAL = "PERSONAL"
    HOME = "HOME"
    EDUCATION = "EDUCATION"
    BUSINESS = "BUSINESS"


class LoanStatus(str, PyEnum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"
    REJECTED = "REJECTED"


class InstallmentStatus(str, PyEnum):
    PENDING = "PENDING"
    PAID = "PAID"
    OVERDUE = "OVERDUE"


class Loan(Base):
    __tablename__ = "loans"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    loan_number: Mapped[str] = mapped_column(
        String(24), unique=True, index=True, nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    disbursement_account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("bank_accounts.id", ondelete="RESTRICT"), nullable=False
    )
    loan_type: Mapped[LoanType] = mapped_column(Enum(LoanType), nullable=False)
    currency: Mapped[CurrencyCode] = mapped_column(
        Enum(CurrencyCode), default=CurrencyCode.INR, nullable=False
    )
    principal_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    annual_interest_rate: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    tenure_months: Mapped[int] = mapped_column(Integer, nullable=False)
    emi_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    outstanding_principal: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    status: Mapped[LoanStatus] = mapped_column(
        Enum(LoanStatus), default=LoanStatus.ACTIVE, nullable=False
    )
    purpose: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    installments: Mapped[list["LoanInstallment"]] = relationship(
        back_populates="loan", cascade="all, delete-orphan"
    )


class LoanInstallment(Base):
    __tablename__ = "loan_installments"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    loan_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("loans.id", ondelete="CASCADE"), index=True, nullable=False
    )
    installment_number: Mapped[int] = mapped_column(Integer, nullable=False)
    due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    emi_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    principal_component: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    interest_component: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    penalty_amount: Mapped[Decimal] = mapped_column(
        Numeric(19, 4), default=Decimal("0.0000"), nullable=False
    )
    remaining_balance: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    status: Mapped[InstallmentStatus] = mapped_column(
        Enum(InstallmentStatus), default=InstallmentStatus.PENDING, nullable=False
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    loan: Mapped["Loan"] = relationship(back_populates="installments")