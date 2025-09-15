import functools
from types import SimpleNamespace
from typing import Any
from unittest import mock

import jwt
import requests

from simple_oauth2.settings import OAuth2ProviderSettings

CONFIGURATION_RESPONSE = {
    "authorization_endpoint": "https://example.com/authorize",
    "token_endpoint": "https://example.com/token",
    "userinfo_endpoint": "https://example.com/userinfo",
    "jwks_uri": "https://example.com/.well-known/jwks.json",
    "end_session_endpoint": "https://example.com/logout",
    "login_endpoint": "https://example.com/login",
    "id_token_signing_alg_values_supported": ["plain", "HS256"],
}

SIMPLE_OAUTH2_SETTINGS = {
    "pkce-plain": {
        "CLIENT_ID": "pkce-plain",
        "CLIENT_SECRET": "pkce-plain",
        "BASE_URL": "https://example.com",
        "REDIRECT_URI": "https://example.com/callback",
        "POST_LOGOUT_REDIRECT_URI": "https://example.com/logout",
        "CODE_CHALLENGE_METHOD": "plain",
    },
    "pkce-s256": {
        "CLIENT_ID": "pkce-s256",
        "CLIENT_SECRET": "pkce-s256",
        "BASE_URL": "https://example.com",
        "REDIRECT_URI": "https://example.com/callback",
        "POST_LOGOUT_REDIRECT_URI": "https://example.com/logout",
        "CODE_CHALLENGE_METHOD": "s256",
    },
    "pkce-unknown-alg": {
        "CLIENT_ID": "pkce-s256",
        "CLIENT_SECRET": "pkce-s256",
        "BASE_URL": "https://example.com",
        "REDIRECT_URI": "https://example.com/callback",
        "POST_LOGOUT_REDIRECT_URI": "https://example.com/logout",
        "CODE_CHALLENGE_METHOD": "unknown",
    },
    "no-pkce": {
        "CLIENT_ID": "no-pkce",
        "CLIENT_SECRET": "no-pkce",
        "BASE_URL": "https://example.com",
        "REDIRECT_URI": "https://example.com/callback",
        "POST_LOGOUT_REDIRECT_URI": "https://example.com/logout",
        "USE_PKCE": False,
    },
    "extra-params": {
        "CLIENT_ID": "extra-params",
        "CLIENT_SECRET": "extra-params",
        "BASE_URL": "https://example.com",
        "REDIRECT_URI": "https://example.com/callback",
        "POST_LOGOUT_REDIRECT_URI": "https://example.com/logout",
        "USE_PKCE": False,
        "AUTHORIZATION_EXTRA_PARAMETERS": {"foo": "bar", "baz": "qux"},
    },
    "token-fails": {
        "CLIENT_ID": "token-fails",
        "CLIENT_SECRET": "token-fails",
        "BASE_URL": "https://example.com",
        "REDIRECT_URI": "https://example.com/callback",
        "POST_LOGOUT_REDIRECT_URI": "https://example.com/logout",
        "USE_PKCE": False,
        "TOKEN_PATH": "/unknown",
    },
    "userinfo-fails": {
        "CLIENT_ID": "userinfo-fails",
        "CLIENT_SECRET": "userinfo-fails",
        "BASE_URL": "https://example.com",
        "REDIRECT_URI": "https://example.com/callback",
        "POST_LOGOUT_REDIRECT_URI": "https://example.com/logout",
        "USE_PKCE": False,
        "USERINFO_PATH": "/unknown",
    },
}


def raise_request_exception():
    """Helper to raise a requests.RequestException from a lambda."""
    raise requests.RequestException(response=SimpleNamespace(status_code="404", content='{"detail": "error"}'.encode()))


def mocked_requests(method, url, data=None, **kwargs):
    """Mocked requests.request return values."""
    match (method.upper(), url):
        case "GET", "https://example.com/.well-known/openid-configuration":
            return SimpleNamespace(
                status_code="200", json=lambda: CONFIGURATION_RESPONSE, raise_for_status=lambda: None
            )
        case "POST", "https://example.com/token":
            return SimpleNamespace(
                status_code="200",
                json=lambda: {
                    "access_token": "abcdefghijklmnopqrstuwxz",
                    "id_token": jwt.encode(
                        {
                            "sub": "1234567890",
                            "email": "test@test.com",
                            "preferred_username": "test",
                            "aud": data["code"][:-5],
                        },
                        "key",
                        algorithm="HS256",
                    ),
                },
                raise_for_status=lambda: None,
            )
        case "GET", "https://example.com/userinfo":
            return SimpleNamespace(
                status_code="200",
                json=lambda: {"sub": "1234567890", "email": "test@test.com", "preferred_username": "test"},
                raise_for_status=lambda: None,
            )
        case _:
            return SimpleNamespace(
                status_code="404", json=lambda: {"detail": "Not found."}, raise_for_status=raise_request_exception()
            )


class override_oauth2_settings:
    """Patch 'settings.oauth2_settings' with the provided SIMPLE_OAUTH2 dict."""

    def __init__(self, simple_oauth2: dict):
        self.simple_oauth2 = simple_oauth2

    def __call__(self, func):
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any):
            with mock.patch("requests.api.request", side_effect=mocked_requests):
                new = {alias: OAuth2ProviderSettings(alias, settings) for alias, settings in self.simple_oauth2.items()}
                with mock.patch.dict("simple_oauth2.settings.oauth2_settings", new, clear=True):
                    return func()

        return wrapper
