from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from simple_oauth2.enums import Status
from simple_oauth2.exceptions import UnknownProvider
from simple_oauth2.models import Session
from simple_oauth2.serializers import TokenSerializer
from simple_oauth2.settings import oauth2_settings


class OAuth2ViewSet(viewsets.GenericViewSet):
    """Allows authentication through FranceConnect."""

    authentication_classes: list[type] = []
    permission_classes: list[type] = []
    serializer_class = TokenSerializer

    @action(detail=False, methods=("get",))
    def url(self, request: Request) -> Response:
        """Return the OAuth2 URL the login button must use."""
        if (provider := request.query_params.get("provider")) is None:
            raise ValidationError(
                {"provider": f"OAuth2 provider required, allowed values are: '{', '.join(oauth2_settings)}'"}
            )
        try:
            session = Session.start(provider)
        except UnknownProvider:
            raise ValidationError(
                {
                    "provider": f"Unknown OAuth2 provider '{provider}', allowed values are: '{', '.join(oauth2_settings)}'"
                }
            )
        return Response({"url": session.authentication_url()})

    @action(detail=False, methods=("post",), serializer_class=TokenSerializer)
    def token(self, request: Request) -> Response:
        """Return tokens using the code obtained from your provider."""
        serializer = self.get_serializer(data=self.request.data)
        serializer.is_valid(raise_exception=True)

        try:
            session = Session.objects.get(
                _provider=serializer.validated_data["provider"],
                state=serializer.validated_data["state"],
                status=Status.PENDING,
            )
        except Session.DoesNotExist:
            raise ValidationError({"state": "No ongoing session matches the provided state."})

        oauth2_tokens = session.get_tokens(serializer.validated_data["code"])
        user = session.get_user(**oauth2_tokens)
        payload = session.get_payload(oauth2_tokens, user)
        return Response(payload)
