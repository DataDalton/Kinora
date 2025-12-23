from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import asyncpg
from curl_cffi.requests.errors import RequestsError
import json

from app.db import get_db
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    verify_token,
)
from app.core.config import settings
from app.core.forward_auth import detect_forward_auth
from app.core.oidc import OIDCProvider, create_oidc_provider_from_settings
from app.schemas.user import (
    User,
    UserCreate,
    UserLogin,
    Token,
    LoginResponse,
    TwoFactorChallengeRequest,
    OIDCProviderConfig,
    OIDCProviderPublic,
    OIDCAuthRequest,
    OIDCCallbackRequest,
    LinkAuthProviderRequest,
    UserAuthProvider,
)
from app.core.two_factor import verify_totp_code
import secrets

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


@router.get("/registration-status")
async def get_registration_status(conn: asyncpg.Connection = Depends(get_db)):
    """
    Check if user registration is enabled (public endpoint for login page)
    """
    try:
        registration_enabled = await conn.fetchval(
            "SELECT value FROM app_settings WHERE key = $1",
            "allow_user_registration"
        )
        # Default to enabled if value doesn't exist or is not explicitly 'false'
        return {"enabled": registration_enabled != 'false'}
    except Exception:
        return {"enabled": True}


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    conn: asyncpg.Connection = Depends(get_db),
) -> User:
    """
    Get current authenticated user from token
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = verify_token(token, "access")
    if payload is None:
        raise credentials_exception

    username = payload.get("sub")
    if username is None:
        raise credentials_exception

    user_row = await conn.fetchrow("SELECT * FROM users WHERE username = $1", username)

    if user_row is None:
        raise credentials_exception

    return User(**dict(user_row))


@router.post("/register", response_model=User, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, conn: asyncpg.Connection = Depends(get_db)):
    """
    Register a new user
    """
    # Check if this is the first user (should be administrator)
    user_count = await conn.fetchval("SELECT COUNT(*) FROM users")
    is_first_user = user_count == 0

    # Check if registration is disabled (unless this is the first user)
    if not is_first_user:
        registration_enabled = await conn.fetchval(
            "SELECT value FROM app_settings WHERE key = $1",
            "allow_user_registration"
        )
        if registration_enabled == 'false':
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User registration is currently disabled",
            )

    # Check if username exists
    existing_user = await conn.fetchrow(
        "SELECT id FROM users WHERE username = $1",
        user_data.username,
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )

    user_role = 'administrator' if is_first_user else 'user'

    # Hash password and create user
    hashed_password = get_password_hash(user_data.password)

    user_row = await conn.fetchrow(
        """
        INSERT INTO users (username, hashed_password, is_active, role)
        VALUES ($1, $2, TRUE, $3)
        RETURNING *
        """,
        user_data.username,
        hashed_password,
        user_role,
    )

    return User(**dict(user_row))


@router.post("/login", response_model=LoginResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    conn: asyncpg.Connection = Depends(get_db)
):
    """
    Login with username and password
    Returns tokens directly if no 2FA, or 2FA challenge if 2FA is enabled
    """
    user_row = await conn.fetchrow(
        "SELECT * FROM users WHERE username = $1", form_data.username
    )

    if not user_row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = dict(user_row)

    if not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
        )

    totp_enabled = await conn.fetchval(
        "SELECT enabled FROM user_totp WHERE user_id = $1",
        user["id"],
    )

    webauthn_count = await conn.fetchval(
        "SELECT COUNT(*) FROM user_webauthn_credentials WHERE user_id = $1",
        user["id"],
    )

    if totp_enabled or webauthn_count > 0:
        challenge = secrets.token_urlsafe(32)
        await conn.execute(
            """
            INSERT INTO app_settings (key, value, value_type, category)
            VALUES ($1, $2, 'string', '2fa_challenge')
            ON CONFLICT (key) DO UPDATE SET value = $2, updated_at = NOW()
            """,
            f"2fa_challenge_{user['username']}",
            challenge,
        )

        return LoginResponse(
            requires_2fa=True,
            totp_enabled=bool(totp_enabled),
            webauthn_enabled=webauthn_count > 0,
            challenge=challenge,
        )

    access_token = create_access_token(
        data={"sub": user["username"], "user_id": user["id"]}
    )
    refresh_token = create_refresh_token(
        data={"sub": user["username"], "user_id": user["id"]}
    )

    await conn.execute(
        "UPDATE users SET last_login_at = NOW() WHERE id = $1",
        user["id"],
    )

    return LoginResponse(
        requires_2fa=False,
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/verify-2fa", response_model=Token)
async def verify_two_factor(
    challenge_data: TwoFactorChallengeRequest,
    conn: asyncpg.Connection = Depends(get_db)
):
    """
    Verify 2FA code (TOTP or WebAuthn) and return authentication tokens
    """
    user_row = await conn.fetchrow(
        "SELECT * FROM users WHERE username = $1", challenge_data.username
    )

    if not user_row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid 2FA challenge",
        )

    user = dict(user_row)

    stored_challenge = await conn.fetchval(
        "SELECT value FROM app_settings WHERE key = $1",
        f"2fa_challenge_{challenge_data.username}",
    )

    if not stored_challenge:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No pending 2FA challenge. Please login again.",
        )

    verified = False

    if challenge_data.code:
        totp_data = await conn.fetchrow(
            "SELECT secret, enabled, backup_codes FROM user_totp WHERE user_id = $1",
            user["id"],
        )

        if totp_data and totp_data["enabled"]:
            if verify_totp_code(totp_data["secret"], challenge_data.code):
                verified = True
            else:
                backup_codes = json.loads(totp_data["backup_codes"]) if totp_data["backup_codes"] else []
                if challenge_data.code.upper() in backup_codes:
                    verified = True
                    backup_codes.remove(challenge_data.code.upper())
                    await conn.execute(
                        "UPDATE user_totp SET backup_codes = $1 WHERE user_id = $2",
                        json.dumps(backup_codes),
                        user["id"],
                    )

    elif challenge_data.credential:
        from webauthn import verify_authentication_response
        from webauthn.helpers.structs import AuthenticationCredential

        try:
            credential = AuthenticationCredential.parse_obj(challenge_data.credential)

            cred_data = await conn.fetchrow(
                """
                SELECT id, public_key, sign_count
                FROM user_webauthn_credentials
                WHERE user_id = $1 AND credential_id = $2
                """,
                user["id"],
                credential.raw_id.hex(),
            )

            if cred_data:
                verification = verify_authentication_response(
                    credential=credential,
                    expected_challenge=bytes.fromhex(stored_challenge),
                    expected_rp_id="localhost",
                    expected_origin="http://localhost:3000",
                    credential_public_key=bytes.fromhex(cred_data["public_key"]),
                    credential_current_sign_count=cred_data["sign_count"],
                )

                await conn.execute(
                    """
                    UPDATE user_webauthn_credentials
                    SET sign_count = $1, last_used_at = NOW()
                    WHERE id = $2
                    """,
                    verification.new_sign_count,
                    cred_data["id"],
                )

                verified = True
        except Exception:
            pass

    if not verified:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid 2FA code or credential",
        )

    await conn.execute(
        "DELETE FROM app_settings WHERE key = $1",
        f"2fa_challenge_{challenge_data.username}",
    )

    access_token = create_access_token(
        data={"sub": user["username"], "user_id": user["id"]}
    )
    refresh_token = create_refresh_token(
        data={"sub": user["username"], "user_id": user["id"]}
    )

    await conn.execute(
        "UPDATE users SET last_login_at = NOW() WHERE id = $1",
        user["id"],
    )

    return Token(access_token=access_token, refresh_token=refresh_token)


@router.get("/me", response_model=User)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """
    Get current user information
    """
    return current_user


# Helper functions for SSO/OIDC


async def get_or_create_user_from_provider(
    conn: asyncpg.Connection,
    provider_type: str,
    provider_name: str,
    provider_subject: str,
    username: str,
    metadata: dict = None
) -> tuple[User, bool]:
    """
    Get or create user from auth provider
    Returns tuple of (User, is_new_user)
    """
    auth_provider = await conn.fetchrow(
        """
        SELECT user_id FROM user_auth_providers
        WHERE provider_type = $1 AND provider_name = $2 AND provider_subject = $3
        """,
        provider_type, provider_name, provider_subject
    )

    if auth_provider:
        user_row = await conn.fetchrow(
            "SELECT * FROM users WHERE id = $1",
            auth_provider["user_id"]
        )

        await conn.execute(
            """
            UPDATE user_auth_providers
            SET last_used_at = NOW()
            WHERE provider_type = $1 AND provider_name = $2 AND provider_subject = $3
            """,
            provider_type, provider_name, provider_subject
        )

        await conn.execute(
            "UPDATE users SET last_login_at = NOW() WHERE id = $1",
            auth_provider["user_id"]
        )

        return User(**dict(user_row)), False

    user_count = await conn.fetchval("SELECT COUNT(*) FROM users")
    is_first_user = user_count == 0

    if not is_first_user:
        registration_enabled = await conn.fetchval(
            "SELECT value FROM app_settings WHERE key = $1",
            "allow_user_registration"
        )
        if registration_enabled == 'false':
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User registration is currently disabled",
            )

    existing_user = await conn.fetchrow(
        "SELECT id FROM users WHERE username = $1",
        username
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Username '{username}' is already taken. Please link this provider to your existing account.",
        )

    user_role = 'administrator' if is_first_user else 'user'

    user_row = await conn.fetchrow(
        """
        INSERT INTO users (username, hashed_password, role, last_login_at)
        VALUES ($1, NULL, $2, NOW())
        RETURNING *
        """,
        username,
        user_role,
    )

    await conn.execute(
        """
        INSERT INTO user_auth_providers
        (user_id, provider_type, provider_name, provider_subject, provider_username, provider_metadata)
        VALUES ($1, $2, $3, $4, $5, $6)
        """,
        user_row["id"],
        provider_type,
        provider_name,
        provider_subject,
        username,
        json.dumps(metadata) if metadata else None,
    )

    return User(**dict(user_row)), True


# Forward Auth endpoints


@router.post("/forward-auth", response_model=Token)
async def forward_auth_login(
    request: Request,
    conn: asyncpg.Connection = Depends(get_db)
):
    """
    Handle forward authentication from Authelia/Authentik
    Auto-detects and logs in users based on headers
    """
    trusted_proxies_setting = await conn.fetchval(
        "SELECT value FROM app_settings WHERE key = $1",
        "forward_auth_trusted_proxies"
    )

    trusted_ranges = None
    if trusted_proxies_setting:
        try:
            trusted_ranges = json.loads(trusted_proxies_setting)
        except json.JSONDecodeError:
            trusted_ranges = None

    forward_auth_data = detect_forward_auth(request, trusted_ranges)

    if not forward_auth_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No valid forward authentication headers detected",
        )

    user, is_new = await get_or_create_user_from_provider(
        conn,
        forward_auth_data["provider_type"],
        forward_auth_data["provider_name"],
        forward_auth_data["username"],
        forward_auth_data["username"],
        forward_auth_data.get("metadata"),
    )

    access_token = create_access_token(
        data={"sub": user.username, "user_id": user.id}
    )
    refresh_token = create_refresh_token(
        data={"sub": user.username, "user_id": user.id}
    )

    return Token(access_token=access_token, refresh_token=refresh_token)


# OIDC Provider Management (Admin only)


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """
    Dependency to require administrator role
    """
    if current_user.role != 'administrator':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator privileges required",
        )
    return current_user


@router.get("/oidc/providers", response_model=List[OIDCProviderPublic])
async def list_oidc_providers(conn: asyncpg.Connection = Depends(get_db)):
    """
    List all enabled OIDC providers (public endpoint for login page)
    """
    providers_data = await conn.fetch(
        """
        SELECT key, value FROM app_settings
        WHERE category = 'oidc_provider' AND key LIKE 'oidc_provider_%'
        """
    )

    providers = []
    provider_ids = set()

    for row in providers_data:
        key_parts = row["key"].split("_")
        if len(key_parts) >= 3:
            provider_id = key_parts[2]
            provider_ids.add(provider_id)

    for provider_id in provider_ids:
        try:
            config_json = await conn.fetchval(
                "SELECT value FROM app_settings WHERE key = $1",
                f"oidc_provider_{provider_id}_config"
            )

            if config_json:
                config = json.loads(config_json)
                if config.get("enabled", True):
                    providers.append(OIDCProviderPublic(
                        id=int(provider_id),
                        name=config.get("name", f"Provider {provider_id}"),
                        enabled=True,
                        button_text=config.get("button_text"),
                        button_icon=config.get("button_icon"),
                    ))
        except (json.JSONDecodeError, ValueError):
            continue

    return providers


@router.post("/oidc/providers", response_model=OIDCProviderConfig)
async def create_oidc_provider(
    config: OIDCProviderConfig,
    conn: asyncpg.Connection = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Create a new OIDC provider (admin only)
    """
    next_id = await conn.fetchval(
        """
        SELECT COALESCE(MAX(CAST(SUBSTRING(key FROM 'oidc_provider_([0-9]+)_config') AS INTEGER)), 0) + 1
        FROM app_settings WHERE key LIKE 'oidc_provider_%_config'
        """
    )

    config_dict = config.dict()
    config_dict["id"] = next_id

    await conn.execute(
        """
        INSERT INTO app_settings (key, value, value_type, is_encrypted, category)
        VALUES ($1, $2, 'json', true, 'oidc_provider')
        """,
        f"oidc_provider_{next_id}_config",
        json.dumps(config_dict),
    )

    return OIDCProviderConfig(**config_dict)


@router.put("/oidc/providers/{provider_id}", response_model=OIDCProviderConfig)
async def update_oidc_provider(
    provider_id: int,
    config: OIDCProviderConfig,
    conn: asyncpg.Connection = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Update an OIDC provider (admin only)
    """
    config_dict = config.dict()
    config_dict["id"] = provider_id

    result = await conn.execute(
        """
        UPDATE app_settings
        SET value = $1, updated_at = NOW()
        WHERE key = $2 AND category = 'oidc_provider'
        """,
        json.dumps(config_dict),
        f"oidc_provider_{provider_id}_config",
    )

    if result == "UPDATE 0":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="OIDC provider not found",
        )

    return OIDCProviderConfig(**config_dict)


@router.delete("/oidc/providers/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_oidc_provider(
    provider_id: int,
    conn: asyncpg.Connection = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Delete an OIDC provider (admin only)
    """
    result = await conn.execute(
        """
        DELETE FROM app_settings
        WHERE key = $1 AND category = 'oidc_provider'
        """,
        f"oidc_provider_{provider_id}_config",
    )

    if result == "DELETE 0":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="OIDC provider not found",
        )


# OIDC Authentication Flow


@router.get("/oidc/authorize/{provider_id}")
async def oidc_authorize(
    provider_id: int,
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Get OIDC authorization URL for provider
    """
    config_json = await conn.fetchval(
        "SELECT value FROM app_settings WHERE key = $1",
        f"oidc_provider_{provider_id}_config"
    )

    if not config_json:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="OIDC provider not found",
        )

    config = json.loads(config_json)

    if not config.get("enabled", True):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OIDC provider is disabled",
        )

    provider = OIDCProvider(
        provider_url=config["provider_url"],
        client_id=config["client_id"],
        client_secret=config["client_secret"],
        redirect_uri=config["redirect_uri"],
        scopes=config.get("scopes", "openid profile"),
    )

    auth_url, state = provider.generate_authorization_url()

    await conn.execute(
        """
        INSERT INTO app_settings (key, value, value_type, category)
        VALUES ($1, $2, 'string', 'oidc_state')
        ON CONFLICT (key) DO UPDATE SET value = $2, updated_at = NOW()
        """,
        f"oidc_state_{state}",
        str(provider_id),
    )

    return {"authorization_url": auth_url, "state": state}


@router.post("/oidc/callback", response_model=Token)
async def oidc_callback(
    callback_data: OIDCCallbackRequest,
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Handle OIDC callback with authorization code
    """
    stored_provider_id = await conn.fetchval(
        "SELECT value FROM app_settings WHERE key = $1",
        f"oidc_state_{callback_data.state}"
    )

    if not stored_provider_id or int(stored_provider_id) != callback_data.provider_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid state parameter",
        )

    await conn.execute(
        "DELETE FROM app_settings WHERE key = $1",
        f"oidc_state_{callback_data.state}"
    )

    config_json = await conn.fetchval(
        "SELECT value FROM app_settings WHERE key = $1",
        f"oidc_provider_{callback_data.provider_id}_config"
    )

    if not config_json:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="OIDC provider not found",
        )

    config = json.loads(config_json)

    provider = OIDCProvider(
        provider_url=config["provider_url"],
        client_id=config["client_id"],
        client_secret=config["client_secret"],
        redirect_uri=config["redirect_uri"],
        scopes=config.get("scopes", "openid profile"),
    )

    try:
        tokens = await provider.exchange_code_for_tokens(callback_data.code)
        id_token = tokens.get("id_token")

        if not id_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No ID token received from provider",
            )

        claims = await provider.verify_id_token(id_token)

        if not claims:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid ID token",
            )

        subject = claims.get("sub")
        username = claims.get("preferred_username") or claims.get("email") or subject

        if not subject or not username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing required claims in ID token",
            )

        user, is_new = await get_or_create_user_from_provider(
            conn,
            "oidc",
            config["name"],
            subject,
            username,
            claims,
        )

        access_token = create_access_token(
            data={"sub": user.username, "user_id": user.id}
        )
        refresh_token = create_refresh_token(
            data={"sub": user.username, "user_id": user.id}
        )

        return Token(access_token=access_token, refresh_token=refresh_token)

    except RequestsError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to exchange code for tokens: {str(e)}",
        )


# Account Linking


@router.get("/me/auth-providers", response_model=List[UserAuthProvider])
async def list_user_auth_providers(
    conn: asyncpg.Connection = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all auth providers linked to current user
    """
    providers = await conn.fetch(
        "SELECT * FROM user_auth_providers WHERE user_id = $1",
        current_user.id
    )

    return [UserAuthProvider(**dict(p)) for p in providers]


@router.post("/me/link-provider", response_model=UserAuthProvider)
async def link_auth_provider(
    link_data: LinkAuthProviderRequest,
    conn: asyncpg.Connection = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Link an auth provider to current user account
    """
    existing = await conn.fetchrow(
        """
        SELECT user_id FROM user_auth_providers
        WHERE provider_type = $1 AND provider_name = $2 AND provider_subject = $3
        """,
        link_data.provider_type,
        link_data.provider_name,
        link_data.provider_subject,
    )

    if existing:
        if existing["user_id"] == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This provider is already linked to your account",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This provider is already linked to another account",
            )

    provider_row = await conn.fetchrow(
        """
        INSERT INTO user_auth_providers
        (user_id, provider_type, provider_name, provider_subject)
        VALUES ($1, $2, $3, $4)
        RETURNING *
        """,
        current_user.id,
        link_data.provider_type,
        link_data.provider_name,
        link_data.provider_subject,
    )

    return UserAuthProvider(**dict(provider_row))


@router.delete("/me/auth-providers/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unlink_auth_provider(
    provider_id: int,
    conn: asyncpg.Connection = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Unlink an auth provider from current user account
    """
    provider = await conn.fetchrow(
        "SELECT * FROM user_auth_providers WHERE id = $1 AND user_id = $2",
        provider_id,
        current_user.id,
    )

    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Auth provider not found",
        )

    has_password = await conn.fetchval(
        "SELECT hashed_password IS NOT NULL FROM users WHERE id = $1",
        current_user.id,
    )

    linked_providers_count = await conn.fetchval(
        "SELECT COUNT(*) FROM user_auth_providers WHERE user_id = $1",
        current_user.id,
    )

    if not has_password and linked_providers_count <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot unlink last authentication method. Set a password first.",
        )

    await conn.execute(
        "DELETE FROM user_auth_providers WHERE id = $1",
        provider_id,
    )
