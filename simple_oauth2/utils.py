import secrets
import ssl
import string
import urllib.parse
from typing import Any

import jwt
from django.contrib.auth import get_user_model
from django.db import models
from rest_framework.exceptions import ValidationError

from simple_oauth2.settings import OAuth2ProviderSettings


def generate_nonce(size: int = 128) -> str:
    """Generate a random nonce as an hexadecimal string."""
    return secrets.token_hex(size // 2)


def generate_state(size: int = 128) -> str:
    """Generate a random state as an hexadecimal string."""
    return secrets.token_hex(size // 2)


def generate_code_verifier(size: int = 128) -> str:
    """Generate a random code verifier."""
    if not (43 <= size <= 128):
        raise ValueError("code_verifier must be 43..128 chars (RFC 7636).")
    return "".join(secrets.choice(string.ascii_letters + string.digits + "-._~") for _ in range(size))


def decode_jwt(provider: OAuth2ProviderSettings, token: str) -> dict:
    """Decode a JWT token using the provider's JKWS URI."""
    try:
        ssl_context = ssl._create_unverified_context() if not provider.VERIFY_SSL else None  # nosec: B323
        jwks_client = jwt.PyJWKClient(provider.jwks_uri(), ssl_context=ssl_context, timeout=provider.TIMEOUT)
        key = jwks_client.get_signing_key_from_jwt(token).key
    except jwt.PyJWKClientConnectionError as e:  # pragma: no cover
        raise ValidationError({"__all__": f"Failed to fetch JKWS from the provider: {e}"})
    return jwt.decode(token, key, algorithms=provider.SIGNING_ALGORITHMS, audience=provider.CLIENT_ID)


def get_user(provider: OAuth2ProviderSettings, userinfo: dict, **kwargs: Any) -> models.Model:
    """Create or update a user from the id_token and the userinfo dictionary."""
    from simple_oauth2.models import Sub

    User = get_user_model()

    claims = decode_jwt(provider=provider, token=kwargs["id_token"]) if "id_token" in kwargs else {}
    sub_value = claims.get("sub") or userinfo.get("sub")
    username = (claims.get("preferred_username") or userinfo.get("preferred_username")) or (
        claims.get("email") or userinfo.get("email")
    )
    try:
        sub = Sub.objects.get(_provider=provider.alias, sub=sub_value)
        sub.save(update_fields=["last_login"])  # Update the 'last_login' timestamp
        user = sub.user
    except Sub.DoesNotExist:
        user = User.objects.create_user(username=username)
        Sub.objects.create(user=user, _provider=provider.alias, sub=sub_value)

    user.first_name = claims.get("given_name", "") or userinfo.get("given_name", "")
    user.last_name = claims.get("family_name", "") or userinfo.get("family_name", "")
    user.email = claims.get("email", "") or userinfo.get("email", "")
    user.save()

    return user


def simple_jwt_authenticate(
    provider: OAuth2ProviderSettings, oauth2_tokens: dict[str, str], user: models.Model
) -> dict:
    """Create a simple JWT token payload."""
    from rest_framework_simplejwt.tokens import RefreshToken

    params = {
        "client_id": provider.CLIENT_ID,
        "id_token_hint": oauth2_tokens["id_token"],
        "post_logout_redirect_uri": provider.POST_LOGOUT_REDIRECT_URI,
    }
    url = urllib.parse.urljoin(provider.BASE_URL, provider.LOGOUT_PATH)
    refresh = RefreshToken.for_user(user)
    return {
        "api": {"refresh": str(refresh), "access": str(refresh.access_token)},
        "provider": oauth2_tokens | {"logout_url": f"{url}?{urllib.parse.urlencode(params)}"},
    }
