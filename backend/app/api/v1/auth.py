import random
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user, require_roles
from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    generate_totp_secret,
    get_totp_provisioning_uri,
    hash_password,
    verify_password,
    verify_totp_code,
)
from app.db.session import get_db
from app.models.user import AuditLog, KYCStatus, User, UserRole
from app.schemas.auth import (
    MFASetupResponse,
    MFAVerifyRequest,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication & Security"])
settings = get_settings()

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


async def record_audit(
    db: AsyncSession,
    action: str,
    resource_type: str,
    actor_user_id: str | None = None,
    resource_id: str | None = None,
    ip_address: str | None = None,
    details: str | None = None,
) -> None:
    log = AuditLog(
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=ip_address,
        details=details,
    )
    db.add(log)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_customer(
    payload: UserRegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(select(User).where(User.email == payload.email.lower()))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    customer_code = f"FIN-{random.randint(100000, 999999)}"
    user = User(
        customer_code=customer_code,
        email=payload.email.lower(),
        full_name=payload.full_name.strip(),
        phone_number=payload.phone_number,
        hashed_password=hash_password(payload.password),
        role=UserRole.CUSTOMER,
        kyc_status=KYCStatus.VERIFIED if payload.kyc_document_ref else KYCStatus.PENDING,
        kyc_document_ref=payload.kyc_document_ref,
    )
    db.add(user)
    await db.flush()

    await record_audit(
        db=db,
        action="USER_REGISTERED",
        resource_type="user",
        actor_user_id=user.id,
        resource_id=user.id,
        ip_address=request.client.host if request.client else None,
        details=f"Registered customer {user.customer_code}",
    )
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: UserLoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.email == payload.email.lower()))
    user = result.scalar_one_or_none()
    client_ip = request.client.host if request.client else None

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    now = datetime.now(timezone.utc)
    if user.locked_until and user.locked_until.replace(tzinfo=timezone.utc) > now:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Account temporarily locked due to repeated failed login attempts",
        )

    if not verify_password(payload.password, user.hashed_password):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
            user.locked_until = now + timedelta(minutes=LOCKOUT_MINUTES)
        await record_audit(
            db=db,
            action="LOGIN_FAILED",
            resource_type="user",
            actor_user_id=user.id,
            resource_id=user.id,
            ip_address=client_ip,
            details=f"Failed attempt #{user.failed_login_attempts}",
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if user.mfa_enabled:
        if not payload.mfa_code or not user.mfa_secret or not verify_totp_code(user.mfa_secret, payload.mfa_code):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Valid 6-digit MFA code required",
            )

    user.failed_login_attempts = 0
    user.locked_until = None
    access_token = create_access_token(subject=user.id, role=user.role.value)

    await record_audit(
        db=db,
        action="LOGIN_SUCCESS",
        resource_type="user",
        actor_user_id=user.id,
        resource_id=user.id,
        ip_address=client_ip,
    )
    await db.commit()

    return TokenResponse(
        access_token=access_token,
        expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        role=user.role,
    )


@router.get("/me", response_model=UserResponse)
async def get_my_profile(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/mfa/setup", response_model=MFASetupResponse)
async def setup_mfa(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    secret = generate_totp_secret()
    current_user.mfa_secret = secret
    await db.commit()
    return MFASetupResponse(
        secret=secret,
        provisioning_uri=get_totp_provisioning_uri(secret, current_user.email),
    )


@router.post("/mfa/enable", response_model=UserResponse)
async def enable_mfa(
    payload: MFAVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.mfa_secret or not verify_totp_code(current_user.mfa_secret, payload.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid MFA verification code",
        )
    current_user.mfa_enabled = True
    await record_audit(
        db=db,
        action="MFA_ENABLED",
        resource_type="user",
        actor_user_id=current_user.id,
        resource_id=current_user.id,
    )
    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.get("/admin/users", response_model=list[UserResponse])
async def list_all_users(
    _: User = Depends(require_roles(UserRole.ADMIN, UserRole.AUDITOR)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return list(result.scalars().all())