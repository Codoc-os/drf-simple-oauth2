# Models

## Overview

Internally, `drf-simple-oauth2` uses two models to manage OAuth2 authentication:
`simple_oauth2.models.Session` and `simple_oauth2.models.Sub`.

## Session

The `Session` model represents an OAuth2 authorization session. It lets
`drf-simple-oauth2` track the state of an ongoing OAuth2 flow, from the moment
the authorization URL is generated until the user is authenticated and tokens
are issued.

When a session is started (via `Session.start()`), a new random `state` is
generated, which is expected to be unique for a given provider. The `state`
prevents CSRF during the OAuth2 authorization flow and helps correlate the
callback with the original request.

Sessions have a limited lifetime (configurable via
[`AUTHORIZATION_SESSION_LIFETIME`](settings.md#authorization_session_lifetime)).

You may want to set up a periodic cleanup task to delete expired or otherwise
old sessions. You can filter on the `status` field to remove only sessions that
are failed, expired, or completed.

`status` can have the following values (see `simple_oauth2.enums.Status`):

- `pending`: The URL has been generated, but the call to `/oauth2/token/` has not yet
  been made.
- `completed`: The call to `/oauth2/token/` was successful, and tokens have been issued.
- `token_failed`: The provider denied the authorization request, or an error occurred
  while exchanging the authorization code for tokens.
- `userinfo_failed`: An error occurred while fetching the UserInfo from the provider.
- `expired`: The session has expired.

> **Note**: The status of a session is not automatically set to `expired` at the
> moment it expires. It is marked as such only when `has_expired()` is called. In a
> cleanup job, you can proactively check for expiration using `created_at` or by
> invoking `has_expired()` before deciding to delete a session.

## Sub

The `Sub` model represents a unique user identifier (`sub`) from a given provider.
It is used to quickly find a user who has previously authenticated with a specific
provider, even if fields commonly used for identification (such as `username` or
`email`) have changed at the provider.

A given `sub` is unique **per provider** (i.e., the `(provider, sub)` pair uniquely
identifies an external account).
