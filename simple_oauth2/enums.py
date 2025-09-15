from django.db import models


class Status(models.TextChoices):
    """Valid status values for a Session."""

    PENDING = "pending"
    TOKEN_FAILED = "token_failed"
    USERINFO_FAILED = "userinfo_failed"
    EXPIRED = "expired"
    COMPLETED = "completed"
