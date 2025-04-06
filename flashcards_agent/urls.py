from django.urls import path
from .views import generate_flashcards

urlpatterns = [
    path("generate/", generate_flashcards, name="generate_flashcards"),
]
