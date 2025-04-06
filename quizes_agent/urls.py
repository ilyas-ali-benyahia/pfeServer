
from django.urls import path
from .views import generate_quizzes

urlpatterns = [
    path("generate_quizzes/", generate_quizzes, name="generate_quizes"),
]
