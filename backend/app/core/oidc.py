from typing import Optional, Dict, Any
from jose import jwt, JWTError
from datetime import datetime, timedelta
import secrets

from app.core.http_client import http_get, http_post


class OIDCProvider:
    """
    OIDC provider configuration and token validation
    """

    def __init__(
        self,
        provider_url: str,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        scopes: str = "openid profile",
    ):
        self.provider_url = provider_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.scopes = scopes
        self._discovery_cache: Optional[Dict[str, Any]] = None
        self._jwks_cache: Optional[Dict[str, Any]] = None
        self._cache_time: Optional[datetime] = None

    async def get_discovery_document(self) -> Dict[str, Any]:
        """
        Fetch OIDC discovery document from provider
        Caches for 1 hour
        """
        if self._discovery_cache and self._cache_time:
            if datetime.utcnow() - self._cache_time < timedelta(hours=1):
                return self._discovery_cache

        discovery_url = f"{self.provider_url}/.well-known/openid-configuration"

        response = await http_get(discovery_url, timeout=10)
        response.raise_for_status()
        self._discovery_cache = response.json()
        self._cache_time = datetime.utcnow()
        return self._discovery_cache

    async def get_jwks(self) -> Dict[str, Any]:
        """
        Fetch JSON Web Key Set from provider
        Caches for 1 hour
        """
        if self._jwks_cache and self._cache_time:
            if datetime.utcnow() - self._cache_time < timedelta(hours=1):
                return self._jwks_cache

        discovery = await self.get_discovery_document()
        jwks_uri = discovery.get("jwks_uri")

        if not jwks_uri:
            raise ValueError("OIDC provider discovery document missing jwks_uri")

        response = await http_get(jwks_uri, timeout=10)
        response.raise_for_status()
        self._jwks_cache = response.json()
        return self._jwks_cache

    def generate_authorization_url(self, state: Optional[str] = None) -> tuple[str, str]:
        """
        Generate OIDC authorization URL
        Returns tuple of (authorization_url, state)
        """
        if state is None:
            state = secrets.token_urlsafe(32)

        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": self.scopes,
            "state": state,
        }

        discovery = self.get_discovery_document()
        authorization_endpoint = discovery.get("authorization_endpoint")

        if not authorization_endpoint:
            raise ValueError("OIDC provider discovery document missing authorization_endpoint")

        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        authorization_url = f"{authorization_endpoint}?{query_string}"

        return authorization_url, state

    async def exchange_code_for_tokens(self, code: str) -> Dict[str, Any]:
        """
        Exchange authorization code for tokens
        Returns dict with access_token, id_token, refresh_token, etc.
        """
        discovery = await self.get_discovery_document()
        token_endpoint = discovery.get("token_endpoint")

        if not token_endpoint:
            raise ValueError("OIDC provider discovery document missing token_endpoint")

        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        response = await http_post(token_endpoint, data=data, timeout=10)
        response.raise_for_status()
        return response.json()

    async def verify_id_token(self, id_token: str) -> Optional[Dict[str, Any]]:
        """
        Verify and decode OIDC ID token
        Returns decoded token claims if valid, None otherwise
        """
        try:
            jwks = await self.get_jwks()

            unverified_header = jwt.get_unverified_header(id_token)
            kid = unverified_header.get("kid")

            rsa_key = None
            for key in jwks.get("keys", []):
                if key.get("kid") == kid:
                    rsa_key = key
                    break

            if not rsa_key:
                return None

            payload = jwt.decode(
                id_token,
                rsa_key,
                algorithms=["RS256"],
                audience=self.client_id,
                issuer=self.provider_url,
            )

            if payload.get("exp", 0) < datetime.utcnow().timestamp():
                return None

            return payload

        except JWTError:
            return None
        except Exception:
            return None

    async def get_userinfo(self, access_token: str) -> Optional[Dict[str, Any]]:
        """
        Fetch user info from OIDC provider using access token
        """
        try:
            discovery = await self.get_discovery_document()
            userinfo_endpoint = discovery.get("userinfo_endpoint")

            if not userinfo_endpoint:
                return None

            response = await http_get(
                userinfo_endpoint,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10,
            )
            response.raise_for_status()
            return response.json()

        except Exception:
            return None


async def create_oidc_provider_from_settings(provider_settings: Dict[str, Any]) -> OIDCProvider:
    """
    Create OIDCProvider instance from database settings
    """
    return OIDCProvider(
        provider_url=provider_settings.get("provider_url"),
        client_id=provider_settings.get("client_id"),
        client_secret=provider_settings.get("client_secret"),
        redirect_uri=provider_settings.get("redirect_uri"),
        scopes=provider_settings.get("scopes", "openid profile"),
    )
