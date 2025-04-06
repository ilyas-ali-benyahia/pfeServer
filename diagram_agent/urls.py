from django.urls import path
from .views import generate_diagram

urlpatterns = [
    path("generate_diagram/", generate_diagram, name="generate_diagram"),
]