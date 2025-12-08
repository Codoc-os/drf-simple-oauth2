import logging
import urllib.parse
from typing import Any, Callable

import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string

logger = logging.getLogger(__name__)

# Default settings for OAuth2 providers
DEFAULTS = {
    "OPENID_CONFIGURATION_PATH": ".well-known/openid-configuration",
    "AUTHORIZATION_SESSION_LIFETIME": 300,  # 5 minutes
    "AUTHORIZATION_EXTRA_PARAMETERS": {},
    "TOKEN_USERINFO_HANDLER": "simple_oauth2.utils.get_user",
    "TOKEN_PAYLOAD_HANDLER": "simple_oauth2.utils.simple_jwt_authenticate",
    "CODE_CHALLENGE_METHOD": "S256",
    "SCOPES": ["openid", "profile", "email"],
    "USE_PKCE": True,
    "VERIFY_SSL": True,
    "TIMEOUT": 5,
    "ALLOW_REDIRECTS": True,
}

# Mapping of settings to OpenID Connect configuration keys
CONFIGURATION_KEY = {
    "AUTHORIZATION_PATH": "authorization_endpoint",
    "TOKEN_PATH": "token_endpoint",
    "USERINFO_PATH": "userinfo_endpoint",
    "LOGOUT_PATH": "end_session_endpoint",
    "JWKS_PATH": "jwks_uri",
    "SIGNING_ALGORITHMS": "id_token_signing_alg_values_supported",
}

# Settings that may be imported from strings
IMPORT_STRINGS = {"TOKEN_USERINFO_HANDLER", "TOKEN_PAYLOAD_HANDLER"}

# Mandatory settings that must be either loaded from OpenID configuration,
# or provided by the user
MANDATORY = {
    "CLIENT_ID",
    "CLIENT_SECRET",
    "REDIRECT_URI",
    "POST_LOGOUT_REDIRECT_URI",
    "BASE_URL",
    "AUTHORIZATION_PATH",
    "TOKEN_PATH",
    "USERINFO_PATH",
    "JWKS_PATH",
    "LOGOUT_PATH",
    "SIGNING_ALGORITHMS",
}


def import_from_string(v: str, provider: str, setting_name: str) -> type:
    """Attempt to import a class from a string representation."""
    try:
        return import_string(v)
    except ImportError as e:  # pragma: no cover
        raise ImportError(
            f"Could not import {v} for SIMPLE_OAUTH2 setting '{provider}[{setting_name}]' {e.__class__.__name__}: {e}."
        )


class OAuth2ProviderSettings:
    """
    A settings object, that allows OAuth2 Provider settings to be accessed as properties.

    Any setting with string import paths will be automatically resolved
    and return the class, rather than the string literal.
    """

    def __init__(self, alias: str, user_settings: dict):
        self._alias = alias

        # Try retrieving some settings from the provider's OpenID configuration
        user_settings = DEFAULTS | user_settings
        url = urllib.parse.urljoin(user_settings["BASE_URL"], user_settings["OPENID_CONFIGURATION_PATH"])
        provider_settings = self._load_settings_from_provider(
            url, user_settings["TIMEOUT"], user_settings["VERIFY_SSL"], user_settings["ALLOW_REDIRECTS"]
        )

        settings = provider_settings | user_settings
        if missing := MANDATORY - {k for k, v in settings.items() if v}:  # pragma: no cover
            raise ImproperlyConfigured(
                f"OAuth2 provider '{self.alias}' is missing mandatory settings: {', '.join(missing)}"
            )

        self._user_settings = settings

    def __getattr__(self, attr: str) -> Any:
        """Return the setting value or raise an AttributeError."""
        if attr not in self._user_settings:  # pragma: no cover
            raise AttributeError(f"Invalid SIMPLE_OAUTH2 setting: '{self.alias}[{attr}]'")
        if attr in IMPORT_STRINGS:
            return self._perform_import(self._user_settings[attr], attr)
        return self._user_settings[attr]

    def _load_settings_from_provider(
        self, url: str, timeout: int, verify: bool, allow_redirects: bool
    ) -> dict[str, Any]:
        """Load settings from the provider's OpenID configuration endpoint."""
        try:
            response = requests.get(url, timeout=timeout, verify=verify, allow_redirects=allow_redirects)
            response.raise_for_status()
        except requests.RequestException as e:  # pragma: no cover
            logger.warning("Could not fetch '%s' OpenID configuration from '%s': %s", self.alias, url, e)
            return {}
        configuration = response.json()
        return {setting: configuration[path] for setting, path in CONFIGURATION_KEY.items()}

    def _perform_import(self, value: str, setting_name: str) -> Callable:  # pragma: no cover
        """Import a class from a string representation."""
        if isinstance(value, str):
            return import_from_string(value, self.alias, setting_name)
        elif isinstance(value, Callable):
            return value
        raise ImproperlyConfigured(
            f"SIMPLE_OAUTH2 setting '{self.alias}[{setting_name}]' must be a string or callable."
        )

    @property
    def alias(self) -> str:
        """Return the provider alias."""
        return self._alias

    def jwks_uri(self) -> str:
        """Return the full JWKS URL."""
        return urllib.parse.urljoin(self.BASE_URL, self.JWKS_PATH)

    def authorization_uri(self) -> str:
        """Return the full authorization URL."""
        return urllib.parse.urljoin(self.BASE_URL, self.AUTHORIZATION_PATH)

    def token_uri(self) -> str:
        """Return the full token URL."""
        return urllib.parse.urljoin(self.BASE_URL, self.TOKEN_PATH)

    def userinfo_uri(self) -> str:
        """Return the full token URL."""
        return urllib.parse.urljoin(self.BASE_URL, self.USERINFO_PATH)


oauth2_settings = {
    alias: OAuth2ProviderSettings(alias, settings) for alias, settings in getattr(settings, "SIMPLE_OAUTH2", {}).items()
}
