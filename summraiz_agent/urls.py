
from django.urls import path
from .views import generate_summary

urlpatterns = [
    path("generate_summary/",generate_summary , name="generate_summary"),
]
