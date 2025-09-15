from contextlib import contextmanager
from datetime import timedelta
from typing import Any, Callable, TypeVar

import pytest
from django.db import models
from django.utils import timezone

from simple_oauth2.exceptions import SimpleOAuth2Error, UnknownProvider
from simple_oauth2.models import Session
from simple_oauth2.utils import generate_state
from tests.conftest import SIMPLE_OAUTH2_SETTINGS, override_oauth2_settings

STATE1 = generate_state()
STATE2 = generate_state()

T = TypeVar("T")


@contextmanager
def override_field_default(model: type[models.Model], field_name: str, default: Callable[[], Any]):
    field = model._meta.get_field(field_name)
    old = field.default
    try:
        field._get_default = default
        field.default = default
        yield
    finally:
        field.default = old
        field._get_default = old


class ValuesDefault:
    """Callable class to return values from a list one after the other."""

    def __init__(self, values: list[T]):
        self.values = values
        self.index = 0

    def __call__(self) -> T:
        value = self.values[self.index]
        self.index = (self.index + 1) % len(self.values)
        return value


@pytest.mark.django_db
@override_oauth2_settings(SIMPLE_OAUTH2_SETTINGS)
def test_start_multiple_try():
    with override_field_default(Session, "state", ValuesDefault([STATE1] * 5 + [STATE2])):
        session = Session.start("no-pkce")
        assert session.state == STATE1
        session2 = Session.start("no-pkce")
        assert session2.state == STATE2


@pytest.mark.django_db
@override_oauth2_settings(SIMPLE_OAUTH2_SETTINGS)
def test_start_integrity_error():
    with override_field_default(Session, "state", ValuesDefault([STATE1] * 11)):
        Session.start("no-pkce")
        with pytest.raises(
            SimpleOAuth2Error, match="Could not create a unique authorization session after 10 attempts."
        ):
            Session.start("no-pkce")


@override_oauth2_settings(SIMPLE_OAUTH2_SETTINGS)
def test_provider_unknown():
    session = Session(_provider="unknown")
    with pytest.raises(UnknownProvider, match="Unknown OAuth2 provider 'unknown'"):
        _ = session.provider


@override_oauth2_settings(SIMPLE_OAUTH2_SETTINGS)
def test_has_expired():
    session = Session(_provider="no-pkce", created_at=timezone.now())
    assert not session.has_expired()
    session.created_at = timezone.now() - timedelta(days=1)
    assert session.has_expired()


@override_oauth2_settings(SIMPLE_OAUTH2_SETTINGS)
def test_has_expired_naive():
    session = Session(_provider="no-pkce", created_at=timezone.now().replace(tzinfo=None))
    assert not session.has_expired()
    session.created_at = (timezone.now() - timedelta(days=1)).replace(tzinfo=None)
    assert session.has_expired()
