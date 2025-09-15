from django.urls import include, path
from rest_framework import routers

from simple_oauth2 import views

app_name = "simple_oauth2"

router = routers.SimpleRouter()
router.register(r"oauth2", views.OAuth2ViewSet, basename="oauth2")

urlpatterns = [
    path("", include(router.urls)),
]
