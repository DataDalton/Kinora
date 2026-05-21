"""
Two-factor authentication endpoints (TOTP and WebAuthn)
"""

from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
import asyncpg
import json
import secrets

from app.db import get_db
from app.core.two_factor import (
    generate_totp_secret,
    generate_totp_uri,
    verify_totp_code,
    generate_backup_codes,
    generate_qr_code_data_url,
)
from app.schemas.user import (
    User,
    TOTPSetupResponse,
    TOTPVerifyRequest,
    TOTPStatusResponse,
    WebAuthnCredential,
    WebAuthnRegisterRequest,
    WebAuthnRegisterResponse,
    WebAuthnRegisterVerifyRequest,
    TwoFactorStatusResponse,
)
from app.api.v1.endpoints.auth import get_current_user

router = APIRouter()


# TOTP Endpoints


@router.get("/totp/status", response_model=TOTPStatusResponse)
async def get_totp_status(
    conn: asyncpg.Connection = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get current user's TOTP status
    """
    totp_data = await conn.fetchrow(
        "SELECT enabled, created_at, verified_at FROM user_totp WHERE user_id = $1",
        current_user.id,
    )

    if not totp_data:
        return TOTPStatusResponse(enabled=False)

    return TOTPStatusResponse(
        enabled=totp_data["enabled"],
        created_at=totp_data["created_at"],
        verified_at=totp_data["verified_at"],
    )


@router.post("/totp/setup", response_model=TOTPSetupResponse)
async def setup_totp(
    conn: asyncpg.Connection = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate TOTP secret and QR code for setup
    """
    existing = await conn.fetchrow(
        "SELECT enabled FROM user_totp WHERE user_id = $1",
        current_user.id,
    )

    if existing and existing["enabled"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="TOTP is already enabled. Disable it first to re-setup.",
        )

    secret = generate_totp_secret()
    uri = generate_totp_uri(secret, current_user.username)
    qr_code_url = generate_qr_code_data_url(uri)
    backup_codes = generate_backup_codes()

    if existing:
        await conn.execute(
            """
            UPDATE user_totp
            SET secret = $1, enabled = FALSE, backup_codes = $2, verified_at = NULL
            WHERE user_id = $3
            """,
            secret,
            json.dumps(backup_codes),
            current_user.id,
        )
    else:
        await conn.execute(
            """
            INSERT INTO user_totp (user_id, secret, enabled, backup_codes)
            VALUES ($1, $2, FALSE, $3)
            """,
            current_user.id,
            secret,
            json.dumps(backup_codes),
        )

    return TOTPSetupResponse(secret=secret, qr_code_url=qr_code_url, backup_codes=backup_codes)


@router.post("/totp/verify")
async def verify_totp_setup(
    verify_data: TOTPVerifyRequest,
    conn: asyncpg.Connection = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Verify TOTP code and enable TOTP for user
    """
    totp_data = await conn.fetchrow(
        "SELECT secret, enabled FROM user_totp WHERE user_id = $1",
        current_user.id,
    )

    if not totp_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="TOTP not set up. Call /totp/setup first.",
        )

    if not verify_totp_code(totp_data["secret"], verify_data.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid TOTP code",
        )

    await conn.execute(
        """
        UPDATE user_totp
        SET enabled = TRUE, verified_at = NOW()
        WHERE user_id = $1
        """,
        current_user.id,
    )

    return {"message": "TOTP enabled successfully"}


@router.post("/totp/disable")
async def disable_totp(
    verify_data: TOTPVerifyRequest,
    conn: asyncpg.Connection = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Disable TOTP for user (requires current TOTP code or backup code)
    """
    totp_data = await conn.fetchrow(
        "SELECT secret, enabled, backup_codes FROM user_totp WHERE user_id = $1",
        current_user.id,
    )

    if not totp_data or not totp_data["enabled"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="TOTP is not enabled",
        )

    valid_code = verify_totp_code(totp_data["secret"], verify_data.code)

    if not valid_code:
        backup_codes = json.loads(totp_data["backup_codes"]) if totp_data["backup_codes"] else []
        if verify_data.code.upper() not in backup_codes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid TOTP code or backup code",
            )

    await conn.execute(
        "DELETE FROM user_totp WHERE user_id = $1",
        current_user.id,
    )

    return {"message": "TOTP disabled successfully"}


# WebAuthn Endpoints


@router.get("/webauthn/credentials", response_model=List[WebAuthnCredential])
async def list_webauthn_credentials(
    conn: asyncpg.Connection = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all WebAuthn credentials for current user
    """
    credentials = await conn.fetch(
        "SELECT id, credential_id, name, created_at, last_used_at FROM user_webauthn_credentials WHERE user_id = $1",
        current_user.id,
    )

    return [WebAuthnCredential(**dict(c)) for c in credentials]


@router.post("/webauthn/register/start", response_model=WebAuthnRegisterResponse)
async def start_webauthn_registration(
    request_data: WebAuthnRegisterRequest,
    conn: asyncpg.Connection = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Start WebAuthn registration process
    """
    from webauthn import generate_registration_options, options_to_json
    from webauthn.helpers.structs import (
        AuthenticatorAttachment,
        AuthenticatorSelectionCriteria,
        PublicKeyCredentialDescriptor,
        UserVerificationRequirement,
    )

    existing_credentials = await conn.fetch(
        "SELECT credential_id FROM user_webauthn_credentials WHERE user_id = $1",
        current_user.id,
    )

    exclude_credentials = [
        PublicKeyCredentialDescriptor(id=bytes.fromhex(cred["credential_id"])) for cred in existing_credentials
    ]

    options = generate_registration_options(
        rp_id="localhost",
        rp_name="Kinora",
        user_id=str(current_user.id).encode("utf-8"),
        user_name=current_user.username,
        user_display_name=current_user.username,
        exclude_credentials=exclude_credentials,
        authenticator_selection=AuthenticatorSelectionCriteria(
            authenticator_attachment=AuthenticatorAttachment.CROSS_PLATFORM,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
    )

    challenge = options.challenge.hex()
    await conn.execute(
        """
        INSERT INTO app_settings (key, value, value_type, category)
        VALUES ($1, $2, 'string', 'webauthn_challenge')
        ON CONFLICT (key) DO UPDATE SET value = $2, updated_at = NOW()
        """,
        f"webauthn_challenge_{current_user.id}",
        challenge,
    )

    return WebAuthnRegisterResponse(options=json.loads(options_to_json(options)))


@router.post("/webauthn/register/verify")
async def verify_webauthn_registration(
    verify_data: WebAuthnRegisterVerifyRequest,
    conn: asyncpg.Connection = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Verify WebAuthn registration and store credential
    """
    from webauthn import verify_registration_response
    from webauthn.helpers.structs import RegistrationCredential

    stored_challenge = await conn.fetchval(
        "SELECT value FROM app_settings WHERE key = $1",
        f"webauthn_challenge_{current_user.id}",
    )

    if not stored_challenge:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No pending registration challenge",
        )

    try:
        credential = RegistrationCredential.parse_obj(verify_data.credential)

        verification = verify_registration_response(
            credential=credential,
            expected_challenge=bytes.fromhex(stored_challenge),
            expected_rp_id="localhost",
            expected_origin="http://localhost:3000",
        )

        await conn.execute(
            """
            INSERT INTO user_webauthn_credentials
            (user_id, credential_id, public_key, name, sign_count)
            VALUES ($1, $2, $3, $4, $5)
            """,
            current_user.id,
            verification.credential_id.hex(),
            verification.credential_public_key.hex(),
            verify_data.name or "Security Key",
            verification.sign_count,
        )

        await conn.execute(
            "DELETE FROM app_settings WHERE key = $1",
            f"webauthn_challenge_{current_user.id}",
        )

        return {"message": "WebAuthn credential registered successfully"}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to verify registration: {str(e)}",
        )


@router.delete("/webauthn/credentials/{credential_id}")
async def delete_webauthn_credential(
    credential_id: int,
    conn: asyncpg.Connection = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a WebAuthn credential
    """
    result = await conn.execute(
        "DELETE FROM user_webauthn_credentials WHERE id = $1 AND user_id = $2",
        credential_id,
        current_user.id,
    )

    if result == "DELETE 0":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credential not found",
        )

    return {"message": "Credential deleted successfully"}


# 2FA Status


@router.get("/status", response_model=TwoFactorStatusResponse)
async def get_two_factor_status(
    conn: asyncpg.Connection = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get user's 2FA status (both TOTP and WebAuthn)
    """
    totp_enabled = await conn.fetchval(
        "SELECT enabled FROM user_totp WHERE user_id = $1",
        current_user.id,
    )

    webauthn_count = await conn.fetchval(
        "SELECT COUNT(*) FROM user_webauthn_credentials WHERE user_id = $1",
        current_user.id,
    )

    return TwoFactorStatusResponse(
        totp_enabled=bool(totp_enabled),
        webauthn_enabled=webauthn_count > 0,
        webauthn_credentials_count=webauthn_count,
    )
