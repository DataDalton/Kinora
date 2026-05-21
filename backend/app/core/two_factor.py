"""
Two-factor authentication utilities for TOTP and WebAuthn
"""

import pyotp
import secrets
import json
from typing import List, Optional
import io
import base64


def generate_totp_secret() -> str:
    """
    Generate a random TOTP secret
    """
    return pyotp.random_base32()


def generate_totp_uri(secret: str, username: str, issuer: str = "Kinora") -> str:
    """
    Generate TOTP provisioning URI for QR code
    """
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=username, issuer_name=issuer)


def verify_totp_code(secret: str, code: str) -> bool:
    """
    Verify a TOTP code against the secret
    """
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)


def generate_backup_codes(count: int = 10) -> List[str]:
    """
    Generate backup recovery codes
    """
    return [secrets.token_hex(4).upper() for _ in range(count)]


def generate_qr_code_data_url(uri: str) -> str:
    """
    Generate QR code as data URL for frontend display
    """
    try:
        import qrcode

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(uri)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        img_data = base64.b64encode(buffer.getvalue()).decode()
        return f"data:image/png;base64,{img_data}"
    except Exception as e:
        return None
