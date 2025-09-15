class SimpleOAuth2Error(Exception):
    """Base exception for simple_oauth2's exceptions."""


class UnknownProvider(SimpleOAuth2Error):
    """Raised when an unknown OAuth2 provider is referenced."""

    def __init__(self, provider: str):
        self.provider = provider
        super().__init__(f"Unknown OAuth2 provider '{provider}'")
