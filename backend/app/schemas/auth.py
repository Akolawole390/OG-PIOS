from pydantic import BaseModel, EmailStr, Field


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str | None = None


class MessageResponse(BaseModel):
    message: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    message: str
    # Populated only when ENVIRONMENT=development and a real, active account matched the
    # submitted email — see routers/auth.py. Never populated in any other case.
    debug_token: str | None = None
    debug_reset_url: str | None = None


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8)


class SendVerificationResponse(BaseModel):
    message: str
    debug_token: str | None = None
    debug_verify_url: str | None = None


class VerifyEmailRequest(BaseModel):
    token: str
