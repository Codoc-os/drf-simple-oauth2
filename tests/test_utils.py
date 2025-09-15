import pytest
from django.contrib.auth import get_user_model

from simple_oauth2.models import Sub
from simple_oauth2.settings import oauth2_settings
from simple_oauth2.utils import generate_code_verifier, get_user
from tests.conftest import SIMPLE_OAUTH2_SETTINGS, override_oauth2_settings


def test_generate_code_verifier():
    assert generate_code_verifier()
    with pytest.raises(ValueError):
        generate_code_verifier(10)
    with pytest.raises(ValueError):
        generate_code_verifier(200)


@pytest.mark.django_db
@override_oauth2_settings(SIMPLE_OAUTH2_SETTINGS)
def test_get_user():
    user = get_user(
        provider=oauth2_settings["no-pkce"],
        userinfo={
            "sub": "123456",
            "preferred_username": "user",
            "email": "test@test.com",
        },
    )
    assert Sub.objects.filter(sub="123456").exists()
    assert user.username == "user"
    assert user.email == "test@test.com"


@pytest.mark.django_db
@override_oauth2_settings(SIMPLE_OAUTH2_SETTINGS)
def test_get_user_through_sub():
    created = get_user_model().objects.create(username="user1", email="test@test.com")
    Sub.objects.create(user=created, _provider="no-pkce", sub="123456")
    got = get_user(
        provider=oauth2_settings["no-pkce"],
        userinfo={
            "sub": "123456",
            "preferred_username": "user2",  # Use another username to ensure sub is used
            "email": "test@test.com",
        },
    )
    assert created.pk == got.pk
