import uuid
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum as PyEnum
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.session import Base


class AccountType(str, PyEnum):
    SAVINGS = "SAVINGS"
    CURRENT = "CURRENT"
    SALARY = "SALARY"
    SYSTEM_CLEARING = "SYSTEM_CLEARING"


class AccountStatus(str, PyEnum):
    ACTIVE = "ACTIVE"
    FROZEN = "FROZEN"
    CLOSED = "CLOSED"


class CurrencyCode(str, PyEnum):
    INR = "INR"
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"


class EntryDirection(str, PyEnum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class BankAccount(Base):
    __tablename__ = "bank_accounts"
    __table_args__ = (
        CheckConstraint("available_balance >= 0", name="ck_available_balance_non_negative"),
        CheckConstraint("ledger_balance >= 0", name="ck_ledger_balance_non_negative"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    account_number: Mapped[str] = mapped_column(
        String(20), unique=True, index=True, nullable=False
    )
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=True
    )
    account_type: Mapped[AccountType] = mapped_column(
        Enum(AccountType), default=AccountType.SAVINGS, nullable=False
    )
    currency: Mapped[CurrencyCode] = mapped_column(
        Enum(CurrencyCode), default=CurrencyCode.INR, nullable=False
    )
    status: Mapped[AccountStatus] = mapped_column(
        Enum(AccountStatus), default=AccountStatus.ACTIVE, nullable=False
    )
    interest_rate_annual: Mapped[Decimal] = mapped_column(
        Numeric(6, 4), default=Decimal("0.0400"), nullable=False
    )
    available_balance: Mapped[Decimal] = mapped_column(
        Numeric(19, 4), default=Decimal("0.0000"), nullable=False
    )
    ledger_balance: Mapped[Decimal] = mapped_column(
        Numeric(19, 4), default=Decimal("0.0000"), nullable=False
    )
    nickname: Mapped[str | None] = mapped_column(String(80), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class JournalTransaction(Base):
    __tablename__ = "journal_transactions"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_journal_idempotency_key"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    reference_number: Mapped[str] = mapped_column(
        String(32), unique=True, index=True, nullable=False
    )
    idempotency_key: Mapped[str | None] = mapped_column(
        String(128), index=True, nullable=True
    )
    transaction_type: Mapped[str] = mapped_column(
        String(40), index=True, nullable=False
    )
    currency: Mapped[CurrencyCode] = mapped_column(
        Enum(CurrencyCode), default=CurrencyCode.INR, nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    initiated_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    entries: Mapped[list["LedgerEntry"]] = relationship(
        back_populates="journal", cascade="all, delete-orphan"
    )


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_ledger_entry_positive_amount"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    journal_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("journal_transactions.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    account_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("bank_accounts.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    direction: Mapped[EntryDirection] = mapped_column(
        Enum(EntryDirection), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    balance_after: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    journal: Mapped["JournalTransaction"] = relationship(back_populates="entries")