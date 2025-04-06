# server/api/index.py
from django.core.wsgi import get_wsgi_application
import os

# Set Django settings environment variable
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")

# Initialize Django WSGI application
application = get_wsgi_application()

# Serverless function handler
def handler(request, **kwargs):
    return application(request, **kwargs)