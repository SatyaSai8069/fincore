import uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base


class Beneficiary(Base):
    __tablename__ = "beneficiaries"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "beneficiary_account_number",
            name="uq_owner_beneficiary_account",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    owner_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    beneficiary_account_number: Mapped[str] = mapped_column(
        String(20), index=True, nullable=False
    )
    beneficiary_name: Mapped[str] = mapped_column(String(150), nullable=False)
    nickname: Mapped[str | None] = mapped_column(String(80), nullable=True)
    daily_transfer_limit: Mapped[Decimal] = mapped_column(
        Numeric(19, 4), default=Decimal("100000.0000"), nullable=False
    )
    is_verified: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )