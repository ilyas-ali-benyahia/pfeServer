from django.urls import path
from . import views

urlpatterns = [
    path('text/', views.upload_text, name='upload_text'),
    path('chat/', views.chat, name='chat'),
    path('reset/', views.reset, name='reset'),
]