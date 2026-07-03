from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from pydantic import BaseModel, Field, ConfigDict

if TYPE_CHECKING:
    from app.schemas.permission import PermissionGroupSimple


class PermissionGroupSimpleInline(BaseModel):
    """Inline permission group schema to avoid circular imports"""

    id: int
    name: str
    displayName: str = Field(validation_alias="display_name")
    color: Optional[str] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class UserBase(BaseModel):
    """Base user schema"""

    username: str = Field(..., min_length=3, max_length=50)


class UserCreate(UserBase):
    """Schema for creating a new user"""

    password: str = Field(..., min_length=8, max_length=100)


class UserUpdate(BaseModel):
    """Schema for updating a user"""

    username: Optional[str] = Field(None, min_length=3, max_length=50)
    password: Optional[str] = Field(None, min_length=8, max_length=100)
    is_active: Optional[bool] = None


class UserAdminCreate(UserBase):
    """Schema for creating a user by an administrator with group assignments"""

    password: str = Field(..., min_length=8, max_length=100)
    groupIds: List[int] = Field(default_factory=list, description="List of group IDs to assign")
    isActive: bool = Field(default=True)


class UserAdminUpdate(BaseModel):
    """Schema for updating a user by an administrator"""

    username: Optional[str] = Field(None, min_length=3, max_length=50)
    password: Optional[str] = Field(None, min_length=8, max_length=100)
    isActive: Optional[bool] = None
    groupIds: Optional[List[int]] = Field(None, description="List of group IDs to assign")


class UserPasswordReset(BaseModel):
    """Schema for admin resetting a user's password"""

    password: str = Field(..., min_length=8, max_length=100)


class PasswordChange(BaseModel):
    """Schema for user changing their own password"""

    currentPassword: str = Field(..., min_length=1)
    newPassword: str = Field(..., min_length=8, max_length=100)


class UserGroupsUpdate(BaseModel):
    """Schema for setting user group assignments"""

    groupIds: List[int] = Field(..., description="List of group IDs to assign to the user")


class User(UserBase):
    """Schema for user response"""

    id: int
    isActive: bool = Field(validation_alias="is_active")
    groups: List[PermissionGroupSimpleInline] = []
    permissions: List[str] = []
    createdAt: datetime = Field(validation_alias="created_at")
    updatedAt: datetime = Field(validation_alias="updated_at")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class UserLogin(BaseModel):
    """Schema for user login"""

    username: str
    password: str


class Token(BaseModel):
    """Schema for authentication token"""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LoginResponse(BaseModel):
    """Schema for login response with optional 2FA requirement"""

    requires_2fa: bool = False
    totp_enabled: bool = False
    webauthn_enabled: bool = False
    challenge: Optional[str] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Schema for token payload data"""

    username: Optional[str] = None
    user_id: Optional[int] = None


class UserAuthProvider(BaseModel):
    """Schema for linked authentication provider"""

    id: int
    user_id: int
    provider_type: str
    provider_name: Optional[str] = None
    provider_subject: str
    provider_username: Optional[str] = None
    linked_at: datetime
    last_used_at: datetime

    class Config:
        from_attributes = True


class OIDCProviderConfig(BaseModel):
    """Schema for OIDC provider configuration"""

    id: Optional[int] = None
    name: str = Field(..., min_length=1, max_length=100)
    provider_url: str = Field(..., min_length=1)
    client_id: str = Field(..., min_length=1)
    client_secret: str = Field(..., min_length=1)
    redirect_uri: str = Field(..., min_length=1)
    scopes: str = Field(default="openid profile")
    enabled: bool = Field(default=True)
    button_text: Optional[str] = Field(default=None)


class OIDCProviderPublic(BaseModel):
    """Schema for public OIDC provider info (without secrets)"""

    id: int
    name: str
    enabled: bool
    button_text: Optional[str] = None


class OIDCAuthRequest(BaseModel):
    """Schema for OIDC authorization request"""

    provider_id: int


class OIDCCallbackRequest(BaseModel):
    """Schema for OIDC callback with authorization code"""

    provider_id: int
    code: str
    state: str


class LinkAuthProviderRequest(BaseModel):
    """Schema for linking an auth provider to existing account"""

    provider_type: str
    provider_name: str
    provider_subject: str


# 2FA Schemas


class TOTPSetupResponse(BaseModel):
    """Schema for TOTP setup response"""

    secret: str
    qr_code_url: str
    backup_codes: List[str]


class TOTPVerifyRequest(BaseModel):
    """Schema for verifying TOTP code"""

    code: str


class TOTPStatusResponse(BaseModel):
    """Schema for TOTP status"""

    enabled: bool
    created_at: Optional[datetime] = None
    verified_at: Optional[datetime] = None


class WebAuthnCredential(BaseModel):
    """Schema for WebAuthn credential"""

    id: int
    credential_id: str
    name: Optional[str] = None
    created_at: datetime
    last_used_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class WebAuthnRegisterRequest(BaseModel):
    """Schema for WebAuthn registration start"""

    name: Optional[str] = None


class WebAuthnRegisterResponse(BaseModel):
    """Schema for WebAuthn registration response"""

    options: dict


class WebAuthnRegisterVerifyRequest(BaseModel):
    """Schema for verifying WebAuthn registration"""

    credential: dict
    name: Optional[str] = None


class WebAuthnAuthRequest(BaseModel):
    """Schema for WebAuthn authentication start"""

    username: str


class WebAuthnAuthResponse(BaseModel):
    """Schema for WebAuthn authentication response"""

    options: dict
    challenge: str


class WebAuthnAuthVerifyRequest(BaseModel):
    """Schema for verifying WebAuthn authentication"""

    username: str
    credential: dict
    challenge: str


class TwoFactorChallengeRequest(BaseModel):
    """Schema for 2FA challenge after password login"""

    username: str
    code: Optional[str] = None
    credential: Optional[dict] = None


class TwoFactorStatusResponse(BaseModel):
    """Schema for user's 2FA status"""

    totp_enabled: bool
    webauthn_enabled: bool
    webauthn_credentials_count: int


class PermissionGroup(BaseModel):
    """Schema for permission group in user context"""

    id: int
    name: str
    displayName: Optional[str] = Field(default=None, validation_alias="display_name")
    description: Optional[str] = None
    color: Optional[str] = None
    priority: Optional[int] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class UserWithPermissions(UserBase):
    """Schema for user response with permissions data"""

    id: int
    isActive: bool = Field(validation_alias="is_active")
    groups: List[PermissionGroup] = []
    permissions: List[str] = []
    createdAt: datetime = Field(validation_alias="created_at")
    updatedAt: datetime = Field(validation_alias="updated_at")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class UserPermissionsResponse(BaseModel):
    """Schema for effective permissions response"""

    userId: int
    permissions: List[str] = []
