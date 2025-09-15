from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from simple_oauth2.exceptions import SimpleOAuth2Error
from simple_oauth2.models import Session
from simple_oauth2.settings import oauth2_settings
from tests.conftest import SIMPLE_OAUTH2_SETTINGS, override_oauth2_settings


@override_oauth2_settings(SIMPLE_OAUTH2_SETTINGS)
def test_oauth2_url_no_provider():
    client = APIClient()
    response = client.get(reverse("simple_oauth2:oauth2-url"))
    assert response.status_code == 400
    assert response.json() == {
        "provider": f"OAuth2 provider required, allowed values are: '{', '.join(oauth2_settings.keys())}'"
    }


@pytest.mark.django_db
@override_oauth2_settings(SIMPLE_OAUTH2_SETTINGS)
def test_oauth2_url_unknown_provider():
    client = APIClient()
    response = client.get(reverse("simple_oauth2:oauth2-url"), {"provider": "unknown"})
    assert response.status_code == 400
    assert response.json() == {
        "provider": f"Unknown OAuth2 provider 'unknown', allowed values are: '{', '.join(oauth2_settings.keys())}'"
    }


@pytest.mark.django_db
@override_oauth2_settings(SIMPLE_OAUTH2_SETTINGS)
def test_oauth2_url_pkce_unknown_alg():
    client = APIClient()
    with pytest.raises(SimpleOAuth2Error, match="Unknown challenge method: 'unknown'"):
        client.get(reverse("simple_oauth2:oauth2-url"), {"provider": "pkce-unknown-alg"})


@pytest.mark.django_db
@override_oauth2_settings(SIMPLE_OAUTH2_SETTINGS)
def test_oauth2_extra_params_url():
    client = APIClient()
    response = client.get(reverse("simple_oauth2:oauth2-url"), {"provider": "extra-params"})
    assert response.status_code == 200, response.json()
    assert "url" in response.json()
    url = response.json()["url"]
    query_params = parse_qs(urlparse(url).query)
    assert query_params["client_id"] == ["extra-params"]
    assert query_params["response_type"] == ["code"]
    assert query_params["redirect_uri"] == ["https://example.com/callback"]
    assert query_params["scope"] == ["openid profile email"]
    assert "state" in query_params
    assert "nonce" in query_params
    assert "foo" in query_params
    assert query_params["foo"] == ["bar"]
    assert "baz" in query_params
    assert query_params["baz"] == ["qux"]


@pytest.mark.django_db
@override_oauth2_settings(SIMPLE_OAUTH2_SETTINGS)
def test_oauth2_token_unknown_session():
    client = APIClient()
    response = client.post(
        reverse("simple_oauth2:oauth2-token"), {"provider": "pkce", "state": "unknown", "code": "code"}
    )
    assert response.status_code == 400
    assert response.json() == {"state": "No ongoing session matches the provided state."}


@pytest.mark.django_db
@override_oauth2_settings(SIMPLE_OAUTH2_SETTINGS)
def test_oauth2_token_expired():
    client = APIClient()
    response = client.get(reverse("simple_oauth2:oauth2-url"), {"provider": "no-pkce"})
    state = parse_qs(urlparse(response.json()["url"]).query)["state"][0]
    Session.objects.filter(state=state).update(created_at=timezone.now() - timedelta(days=1))
    response = client.post(
        reverse("simple_oauth2:oauth2-token"), {"provider": "no-pkce", "state": state, "code": "no-pkce-code"}
    )
    assert response.status_code == 400
    assert response.json() == {"__all__": "Authorization session has expired."}


@pytest.mark.django_db
@override_oauth2_settings(SIMPLE_OAUTH2_SETTINGS)
def test_oauth2_token_fails():
    client = APIClient()
    response = client.get(reverse("simple_oauth2:oauth2-url"), {"provider": "token-fails"})
    state = parse_qs(urlparse(response.json()["url"]).query)["state"][0]
    response = client.post(
        reverse("simple_oauth2:oauth2-token"), {"provider": "token-fails", "state": state, "code": "token-fails-code"}
    )
    assert response.status_code == 400
    assert response.json() == {"__all__": 'Failed to retrieve tokens from provider: {"detail": "error"}'}


@pytest.mark.django_db
@override_oauth2_settings(SIMPLE_OAUTH2_SETTINGS)
def test_oauth2_userinfo_fails():
    client = APIClient()
    response = client.get(reverse("simple_oauth2:oauth2-url"), {"provider": "userinfo-fails"})
    state = parse_qs(urlparse(response.json()["url"]).query)["state"][0]
    response = client.post(
        reverse("simple_oauth2:oauth2-token"),
        {"provider": "userinfo-fails", "state": state, "code": "userinfo-fails-code"},
    )
    assert response.status_code == 400
    assert response.json() == {"__all__": 'Failed to fetch user info from the provider: {"detail": "error"}.'}


@pytest.mark.django_db
@override_oauth2_settings(SIMPLE_OAUTH2_SETTINGS)
def test_oauth2_without_pkce_url():
    client = APIClient()
    response = client.get(reverse("simple_oauth2:oauth2-url"), {"provider": "no-pkce"})
    assert response.status_code == 200
    assert "url" in response.json()
    url = response.json()["url"]
    query_params = parse_qs(urlparse(url).query)
    assert query_params["client_id"] == ["no-pkce"]
    assert query_params["response_type"] == ["code"]
    assert query_params["redirect_uri"] == ["https://example.com/callback"]
    assert query_params["scope"] == ["openid profile email"]
    assert "state" in query_params
    assert "nonce" in query_params
    assert "code_challenge" not in query_params
    assert "code_challenge_method" not in query_params


@pytest.mark.django_db
@patch("jwt.jwks_client.PyJWKClient.get_signing_key", side_effect=lambda token: SimpleNamespace(key="key"))
@override_oauth2_settings(SIMPLE_OAUTH2_SETTINGS)
def test_oauth2_without_pkce_token():
    client = APIClient()
    response = client.get(reverse("simple_oauth2:oauth2-url"), {"provider": "no-pkce"})
    state = parse_qs(urlparse(response.json()["url"]).query)["state"][0]
    response = client.post(
        reverse("simple_oauth2:oauth2-token"), {"provider": "no-pkce", "state": state, "code": "no-pkce-code"}
    )
    assert response.status_code == 200, response.json()
    data = response.json()
    assert "api" in data
    assert "access" in data["api"]
    assert "refresh" in data["api"]
    assert "provider" in data
    assert "logout_url" in data["provider"]
    assert "id_token" in data["provider"]
    assert "access_token" in data["provider"]


@pytest.mark.django_db
@override_oauth2_settings(SIMPLE_OAUTH2_SETTINGS)
def test_oauth2_with_pkce_plain_url():
    client = APIClient()
    response = client.get(reverse("simple_oauth2:oauth2-url"), {"provider": "pkce-plain"})
    assert response.status_code == 200
    assert "url" in response.json()
    url = response.json()["url"]
    query_params = parse_qs(urlparse(url).query)
    assert query_params["client_id"] == ["pkce-plain"]
    assert query_params["response_type"] == ["code"]
    assert query_params["redirect_uri"] == ["https://example.com/callback"]
    assert query_params["scope"] == ["openid profile email"]
    assert "state" in query_params
    assert "nonce" in query_params
    assert "code_challenge" in query_params
    assert "code_challenge_method" in query_params
    assert query_params["code_challenge_method"] == ["plain"]


@pytest.mark.django_db
@patch("jwt.jwks_client.PyJWKClient.get_signing_key", side_effect=lambda token: SimpleNamespace(key="key"))
@override_oauth2_settings(SIMPLE_OAUTH2_SETTINGS)
def test_oauth2_with_pkce_plain_token():
    client = APIClient()
    response = client.get(reverse("simple_oauth2:oauth2-url"), {"provider": "pkce-plain"})
    state = parse_qs(urlparse(response.json()["url"]).query)["state"][0]
    response = client.post(
        reverse("simple_oauth2:oauth2-token"), {"provider": "pkce-plain", "state": state, "code": "pkce-plain-code"}
    )
    assert response.status_code == 200, response.json()
    data = response.json()
    assert "api" in data
    assert "access" in data["api"]
    assert "refresh" in data["api"]
    assert "provider" in data
    assert "logout_url" in data["provider"]
    assert "id_token" in data["provider"]
    assert "access_token" in data["provider"]


@pytest.mark.django_db
@override_oauth2_settings(SIMPLE_OAUTH2_SETTINGS)
def test_oauth2_with_pkce_s256_url():
    client = APIClient()
    response = client.get(reverse("simple_oauth2:oauth2-url"), {"provider": "pkce-s256"})
    assert response.status_code == 200
    assert "url" in response.json()
    url = response.json()["url"]
    query_params = parse_qs(urlparse(url).query)
    assert query_params["client_id"] == ["pkce-s256"]
    assert query_params["response_type"] == ["code"]
    assert query_params["redirect_uri"] == ["https://example.com/callback"]
    assert query_params["scope"] == ["openid profile email"]
    assert "state" in query_params
    assert "nonce" in query_params
    assert "code_challenge" in query_params
    assert "code_challenge_method" in query_params
    assert query_params["code_challenge_method"] == ["s256"]


@pytest.mark.django_db
@patch("jwt.jwks_client.PyJWKClient.get_signing_key", side_effect=lambda token: SimpleNamespace(key="key"))
@override_oauth2_settings(SIMPLE_OAUTH2_SETTINGS)
def test_oauth2_with_pkce_s256_token():
    client = APIClient()
    response = client.get(reverse("simple_oauth2:oauth2-url"), {"provider": "pkce-s256"})
    state = parse_qs(urlparse(response.json()["url"]).query)["state"][0]
    response = client.post(
        reverse("simple_oauth2:oauth2-token"), {"provider": "pkce-s256", "state": state, "code": "pkce-s256-code"}
    )
    assert response.status_code == 200, response.json()
    data = response.json()
    assert "api" in data
    assert "access" in data["api"]
    assert "refresh" in data["api"]
    assert "provider" in data
    assert "logout_url" in data["provider"]
    assert "id_token" in data["provider"]
    assert "access_token" in data["provider"]
