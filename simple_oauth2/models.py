import base64
import datetime
import hashlib
import urllib.parse
from typing import Any

import requests
from django.contrib.auth import get_user_model
from django.core.exceptions import NON_FIELD_ERRORS
from django.core.validators import RegexValidator
from django.db import IntegrityError, models, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from simple_oauth2 import utils
from simple_oauth2.enums import Status
from simple_oauth2.exceptions import SimpleOAuth2Error, UnknownProvider
from simple_oauth2.settings import OAuth2ProviderSettings, oauth2_settings

PKCE_VALIDATOR = RegexValidator(
    regex=r"^[A-Za-z0-9\-._~]{43,128}$",
    message="code_verifier must be 43–128 chars of unreserved URL characters (RFC 7636).",
)


class Session(models.Model):
    """Represent an OAuth2 authorization session."""

    _provider = models.CharField(max_length=255, db_column="provider")

    nonce = models.CharField(max_length=255, default=utils.generate_nonce)
    state = models.CharField(max_length=255, default=utils.generate_state)
    code_verifier = models.CharField(max_length=128, default=utils.generate_code_verifier, validators=(PKCE_VALIDATOR,))

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True)

    class Meta:
        constraints = (models.UniqueConstraint(fields=("_provider", "state"), name="session_provider_state_key"),)
        indexes = (models.Index(fields=("created_at",)),)

    @classmethod
    def start(cls, provider: str) -> "Session":
        """Try creating a unique Session while avoiding race condition."""
        if provider not in oauth2_settings:
            raise UnknownProvider(provider)
        for _ in range(10):
            try:
                with transaction.atomic():
                    return Session.objects.create(_provider=provider)
            except IntegrityError:
                continue
        raise SimpleOAuth2Error("Could not create a unique authorization session after 10 attempts.")

    @property
    def provider(self) -> OAuth2ProviderSettings:
        """Return the provider configuration associated with this Session."""
        if self._provider in oauth2_settings:
            return oauth2_settings[self._provider]
        raise UnknownProvider(self._provider)

    @property
    def use_pkce(self) -> bool:
        """Return whether or not the Session uses PKCE."""
        return self.provider.USE_PKCE

    @property
    def code_challenge_method(self) -> str:
        """Return the code challenge method associated with this Session."""
        return self.provider.CODE_CHALLENGE_METHOD

    @property
    def code_challenge(self) -> str:
        """Return the code challenge from code_verifier and code_challenge_method."""
        if self.code_challenge_method.lower() == "plain":
            return self.code_verifier

        elif self.code_challenge_method.lower() == "s256":
            digest = hashlib.sha256(self.code_verifier.encode("ascii")).digest()
            return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

        raise SimpleOAuth2Error(f"Unknown challenge method: '{self.code_challenge_method}'")

    def has_expired(self) -> bool:
        """Return whether the authorization session as expired."""
        now = timezone.now().astimezone(datetime.timezone.utc)
        if timezone.is_naive(self.created_at):
            ts = timezone.make_aware(self.created_at, datetime.timezone.utc)
        else:
            ts = self.created_at.astimezone(datetime.timezone.utc)
        if (now - ts).total_seconds() > self.provider.AUTHORIZATION_SESSION_LIFETIME:
            return True
        return False

    def authentication_url(self) -> str:
        """Generate the OAuth2 authentication URL for the given alias."""
        params = {
            "response_type": "code",
            "client_id": self.provider.CLIENT_ID,
            "scope": " ".join(self.provider.SCOPES),
            "nonce": self.nonce,
            "state": self.state,
            "redirect_uri": self.provider.REDIRECT_URI,
        }
        if self.use_pkce:
            params |= {
                "code_challenge": self.code_challenge,
                "code_challenge_method": self.provider.CODE_CHALLENGE_METHOD,
            }
        for key, value in self.provider.AUTHORIZATION_EXTRA_PARAMETERS.items():
            params[key] = value
        return f"{self.provider.authorization_uri()}?{urllib.parse.urlencode(params)}"

    def get_tokens(self, code: str) -> dict[str, str]:
        """Exchange the authorization code for tokens."""
        if self.has_expired():
            self.status = Status.EXPIRED
            self.save(update_fields=["status"])
            raise ValidationError({NON_FIELD_ERRORS: "Authorization session has expired."})

        data = {
            "grant_type": "authorization_code",
            "client_id": self.provider.CLIENT_ID,
            "client_secret": self.provider.CLIENT_SECRET,
            "code": code,
            "redirect_uri": self.provider.REDIRECT_URI,
        }
        if self.use_pkce:
            data["code_verifier"] = self.code_verifier

        try:
            response = requests.post(
                self.provider.token_uri(),
                data=data,
                timeout=self.provider.TIMEOUT,
                verify=self.provider.VERIFY_SSL,
                allow_redirects=self.provider.ALLOW_REDIRECTS,
            )
            response.raise_for_status()
        except requests.RequestException as e:
            self.status = Status.TOKEN_FAILED
            self.save(update_fields=("status",))
            raise ValidationError(
                {"__all__": f"Failed to retrieve tokens from provider: {e.response.content.decode()}"}
            )

        return response.json()

    def get_user(self, access_token: str, **kwargs: Any) -> models.Model:
        """Fetch the user infos from the provider and feet it to the handler."""
        try:
            response = requests.get(
                self.provider.userinfo_uri(),
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=self.provider.TIMEOUT,
                verify=self.provider.VERIFY_SSL,
                allow_redirects=self.provider.ALLOW_REDIRECTS,
            )
            response.raise_for_status()
        except requests.RequestException as e:
            self.status = Status.USERINFO_FAILED
            self.save(update_fields=("status",))
            raise ValidationError(
                {"__all__": f"Failed to fetch user info from the provider: {e.response.content.decode()}."}
            )

        user = self.provider.TOKEN_USERINFO_HANDLER(self.provider, response.json(), **kwargs)

        return user

    def get_payload(self, oauth2_tokens: dict[str, str], user: models.Model) -> dict:
        """Fetch the payload from the provider and feed it to the handler."""
        payload = self.provider.TOKEN_PAYLOAD_HANDLER(self.provider, oauth2_tokens, user)
        self.status = Status.COMPLETED
        self.completed_at = timezone.now()
        self.save(update_fields=("status", "completed_at"))
        return payload


class Sub(models.Model):
    """Link a user to a given OAuth2 provider and its sub."""

    _provider = models.CharField(max_length=255, db_column="provider")
    sub = models.CharField(max_length=255)
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = (models.UniqueConstraint(fields=("_provider", "sub"), name="sub_provider_sub_key"),)
        indexes = (models.Index(fields=("sub",)),)
