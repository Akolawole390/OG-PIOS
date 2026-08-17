import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.security import (
    TokenPurposeError,
    create_access_token,
    create_purpose_token,
    decode_purpose_token,
    hash_password,
    password_fingerprint,
    verify_password,
)
from app.deps import get_current_user
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    MessageResponse,
    ResetPasswordRequest,
    SendVerificationResponse,
    Token,
    VerifyEmailRequest,
)
from app.schemas.user import UserRead
from app.services.audit import AuditAction, record_audit_event
from app.services.mail import send_reset_email, send_verification_email
from app.services.mail_providers.base import MailProvider
from app.services.mail_providers.factory import get_mail_provider_dependency
from app.services.rate_limit import check_email_rate_limit, rate_limiter

router = APIRouter(prefix="/auth", tags=["auth"])

# Same message for every forgot-password/reset-password failure mode (nonexistent email,
# inactive account, expired/garbage/reused token) — never gives an attacker a signal about which
# case occurred. See docs/security.md.
GENERIC_RESET_MESSAGE = "If an account exists for that email, a password reset link has been sent."
INVALID_RESET_TOKEN_MESSAGE = "Invalid or expired reset link."
INVALID_VERIFY_TOKEN_MESSAGE = "Invalid or expired verification link."


@router.post("/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
) -> Token:
    # Throttles credential-stuffing/brute-force attempts against a single account — same
    # sliding-window mechanism as forgot-password, keyed by the submitted email rather than an
    # authenticated user (there isn't one yet at this point).
    check_email_rate_limit("login", form_data.username, limit=10, window_seconds=300)

    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is deactivated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(subject=str(user.id))
    return Token(access_token=access_token)


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.post("/change-password", response_model=MessageResponse)
def change_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessageResponse:
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")

    current_user.hashed_password = hash_password(payload.new_password)
    db.commit()

    record_audit_event(
        db, current_user, AuditAction.PASSWORD_CHANGED, "user", resource_id=current_user.id,
        details="Changed own password",
    )
    return MessageResponse(message="Password changed successfully.")


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(
    payload: ForgotPasswordRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    mail_provider: MailProvider = Depends(get_mail_provider_dependency),
) -> ForgotPasswordResponse:
    """Always returns the same generic message, regardless of whether the email exists or is
    active — anti-enumeration. Only issues a token / sends anything for a real, active account."""
    check_email_rate_limit("forgot-password", payload.email)

    user = db.query(User).filter(User.email == payload.email).first()
    if user is None or not user.is_active:
        return ForgotPasswordResponse(message=GENERIC_RESET_MESSAGE)

    token = create_purpose_token(
        str(user.id), "reset", settings.reset_token_expire_minutes,
        fp=password_fingerprint(user.hashed_password),
    )
    reset_url = f"{settings.frontend_url}/reset-password?token={token}"
    send_reset_email(mail_provider, user, reset_url)

    record_audit_event(
        db, user, AuditAction.PASSWORD_RESET_REQUESTED, "user", resource_id=user.id,
        details="Requested a password reset",
    )

    debug_token = None
    debug_reset_url = None
    if settings.environment == "development":
        debug_token = token
        debug_reset_url = reset_url

    return ForgotPasswordResponse(message=GENERIC_RESET_MESSAGE, debug_token=debug_token, debug_reset_url=debug_reset_url)


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
) -> MessageResponse:
    try:
        token_payload = decode_purpose_token(payload.token, "reset")
    except (jwt.PyJWTError, TokenPurposeError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=INVALID_RESET_TOKEN_MESSAGE) from exc

    user_id = token_payload.get("sub")
    user = db.get(User, int(user_id)) if user_id is not None else None
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=INVALID_RESET_TOKEN_MESSAGE)

    # The token embeds a fingerprint of the hash at issue time — consuming it once (or an
    # intervening password change) changes the hash, so a reused/stale token fails here.
    if token_payload.get("fp") != password_fingerprint(user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=INVALID_RESET_TOKEN_MESSAGE)

    user.hashed_password = hash_password(payload.new_password)
    db.commit()

    record_audit_event(
        db, user, AuditAction.PASSWORD_RESET, "user", resource_id=user.id,
        details="Reset password via emailed link",
    )
    return MessageResponse(message="Password reset successfully. You can now log in with your new password.")


@router.post("/send-verification", response_model=SendVerificationResponse)
def send_verification(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    mail_provider: MailProvider = Depends(get_mail_provider_dependency),
    current_user: User = Depends(rate_limiter("send-verification", limit=3, window_seconds=900)),
) -> SendVerificationResponse:
    if current_user.is_email_verified:
        return SendVerificationResponse(message="Your email is already verified.")

    token = create_purpose_token(str(current_user.id), "verify_email", settings.email_verification_token_expire_minutes)
    verify_url = f"{settings.frontend_url}/verify-email?token={token}"
    send_verification_email(mail_provider, current_user, verify_url)

    record_audit_event(
        db, current_user, AuditAction.EMAIL_VERIFICATION_REQUESTED, "user", resource_id=current_user.id,
        details="Requested email verification",
    )

    debug_token = None
    debug_verify_url = None
    if settings.environment == "development":
        debug_token = token
        debug_verify_url = verify_url

    return SendVerificationResponse(
        message="A verification link has been sent to your email.",
        debug_token=debug_token, debug_verify_url=debug_verify_url,
    )


@router.post("/verify-email", response_model=MessageResponse)
def verify_email(
    payload: VerifyEmailRequest,
    db: Session = Depends(get_db),
) -> MessageResponse:
    try:
        token_payload = decode_purpose_token(payload.token, "verify_email")
    except (jwt.PyJWTError, TokenPurposeError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=INVALID_VERIFY_TOKEN_MESSAGE) from exc

    user_id = token_payload.get("sub")
    user = db.get(User, int(user_id)) if user_id is not None else None
    if user is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=INVALID_VERIFY_TOKEN_MESSAGE)

    if not user.is_email_verified:
        user.is_email_verified = True
        db.commit()
        record_audit_event(
            db, user, AuditAction.EMAIL_VERIFIED, "user", resource_id=user.id,
            details="Verified email address",
        )
    return MessageResponse(message="Email verified successfully.")
