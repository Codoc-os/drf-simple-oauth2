from rest_framework import serializers


class TokenSerializer(serializers.Serializer):
    """Serializer for the token endpoint input data."""

    provider = serializers.CharField()
    code = serializers.CharField()
    state = serializers.CharField()
