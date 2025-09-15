# Settings

## Defining settings

All settings live in a single `SIMPLE_OAUTH2` dictionary.  
Each top-level key is the provider name; each value is a dict of that provider’s settings.

The minimal required settings per provider are: `CLIENT_ID`, `CLIENT_SECRET`, `REDIRECT_URI`,
`POST_LOGOUT_REDIRECT_URI`, and `BASE_URL`.

See below for an example configuration:

```python
SIMPLE_OAUTH2 = {
    "auth0": {
        "CLIENT_ID": "<your-auth0-client-id>",
        "CLIENT_SECRET": "<your-auth0-client-secret>",
        "BASE_URL": "<your-auth0-domain>.<region>.auth0.com",
        "REDIRECT_URI": "http://localhost:8080/app/auth0/callback",
        "POST_LOGOUT_REDIRECT_URI": "http://localhost:8080/app",
    },
    "google": {
        "CLIENT_ID": "<your-google-client-id>",
        "CLIENT_SECRET": "<your-google-client-secret>",
        "BASE_URL": "accounts.google.com",
        "REDIRECT_URI": "http://localhost:8080/app/google/callback",
        "POST_LOGOUT_REDIRECT_URI": "http://localhost:8080/app",
    },
}
```

This assumes the provider exposes the standard OpenID Connect discovery document at
`/.well-known/openid-configuration`. When present, it is used to automatically
populate the remaining required settings: `AUTHORIZATION_PATH`, `TOKEN_PATH`,
`USERINFO_PATH`, `JWKS_PATH`, `LOGOUT_PATH`, and `SIGNING_ALGORITHMS`.

If the provider serves its discovery document at a non-standard path, set
`OPENID_CONFIGURATION_PATH`. If no discovery document is available, you **must**
manually specify all required settings.

Optional settings are listed below.

## Accessing settings

Use `simple_oauth2.settings.oauth2_settings`, which maps provider names to their
resolved settings:

```python
from simple_oauth2.settings import oauth2_settings

auth0_client_id = oauth2_settings["auth0"].CLIENT_ID
```

## Available settings

The following settings are available for each provider.

### `CLIENT_ID`

*Required*

Your OAuth2 client ID.

### `CLIENT_SECRET`

*Required*

Your OAuth2 client secret.

### `BASE_URL`

*Required*

The provider’s base domain.  
Examples: Auth0 — `<your-auth0-domain>.<region>.auth0.com`; Google — `accounts.google.com`.

### `REDIRECT_URI`

*Required*

The URI the provider redirects to after authorization.  
Must match the value registered with the provider.

### `POST_LOGOUT_REDIRECT_URI`

*Required*

The URI the provider redirects to after logout.  
Must match the value registered with the provider.

### `AUTHORIZATION_PATH`

*Required; usually discovered via the provider’s OpenID configuration*

Path to the authorization endpoint, typically `/authorize`.

### `TOKEN_PATH`

*Required; usually discovered via the provider’s OpenID configuration*

Path to the token endpoint, typically `/oauth/token` or `/token`.

### `USERINFO_PATH`

*Required; usually discovered via the provider’s OpenID configuration*

Path to the UserInfo endpoint, typically `/userinfo`.

### `JWKS_PATH`

*Required; usually discovered via the provider’s OpenID configuration*

Path to the JWKS document, typically `/.well-known/jwks.json`.

### `LOGOUT_PATH`

*Required; usually discovered via the provider’s OpenID configuration*

Path to the logout endpoint, typically `/logout`.

### `SIGNING_ALGORITHMS`

*Required; usually discovered via the provider’s OpenID configuration*

List of algorithms used to sign ID tokens, e.g. `["RS256"]`.

### `OPENID_CONFIGURATION_PATH`

*Optional*

Path to the provider’s OpenID configuration document.  
Defaults to `/.well-known/openid-configuration`. Set this if the provider uses a non-standard path.

### `SCOPES`

*Optional*

Scopes requested during authorization.  
Defaults to `["openid", "profile", "email"]`.

### `USE_PKCE`

*Optional*

Whether to use PKCE (Proof Key for Code Exchange).  
Defaults to `True`.

### `CODE_CHALLENGE_METHOD`

*Optional*

PKCE code challenge method.  
Defaults to `S256`. Some providers only support `plain`.

### `AUTHORIZATION_SESSION_LIFETIME`

*Optional*

Lifetime (in seconds) of an authorization session (from URL generation to the call to `/oauth2/token/`).  
Defaults to `300` (5 minutes).

### `AUTHORIZATION_EXTRA_PARAMETERS`

*Optional*

Extra query parameters to include in the authorization URL.  
Some providers require additional parameters.  
Defaults to `{}`.

### `TOKEN_USERINFO_HANDLER`

*Optional*

Callable that creates/updates and returns the authenticated user using the ID token and UserInfo response.  
Defaults to `simple_oauth2.utils.get_user`.

Signature:

```python
def custom_get_user(
    provider,
    userinfo: dict,
    **kwargs: Any,
) -> models.Model:
    ...
```

- `provider`: the provider settings used for authentication.
- `userinfo`: the UserInfo response (dict).
- `kwargs`: may contain additional items such as encoded `id_token` and `access_token`. Do **not** assume these are
  always present. Tokens may include extra claims and can be decoded via `simple_oauth2.utils.decode_token`.

Return a model instance representing the authenticated user.

The contents of `userinfo` and the decoded ID token depend on the provider and requested scopes. At minimum, one of
them should include a `sub` claim that uniquely identifies the user at the provider.

### `TOKEN_PAYLOAD_HANDLER`

*Optional*

Callable that builds the JSON payload returned by the `/oauth2/token/` endpoint.  
Defaults to `simple_oauth2.utils.simple_jwt_authenticate`, which issues JWTs via `djangorestframework-simplejwt` and
returns the provider’s tokens.

Signature:

```python
def custom_token_payload(
    provider,
    oauth2_tokens: dict[str, str],
    user: models.Model,
) -> dict:
    ...
```

- `provider`: the provider settings used for authentication.
- `oauth2_tokens`: tokens returned by the provider (usually `access_token`, `id_token`, and optionally `refresh_token`).
- `user`: the user returned by `TOKEN_USERINFO_HANDLER`.

Return a dict to be serialized as the `/oauth2/token/` response.

It should at least include a valid logout URI (see `simple_oauth2.utils.simple_jwt_authenticate` for an example of
logout URI generation).

### `VERIFY_SSL`

*Optional*

Whether the CA certificate must be verified when using `urllib.request` or
`requests`.  
Default to `True`.

### `TIMEOUT`

*Optional*

The number of seconds waiting for a response before issuing a timeout when using
`urllib.request` or `requests`.  
Default to `5`.

### `ALLOW_REDIRECTS`

*Optional*

Enable / disable redirection when using `urllib.request` or `requests`.  
Default to `True`.
