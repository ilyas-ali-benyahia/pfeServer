from django.urls import path
from .views import upload_and_extract

urlpatterns = [
    path("upload/", upload_and_extract, name="upload"),
   

]
