# استخدم صورة رسمية من Python
FROM python:3.10-slim

# تثبيت الأدوات الأساسية لدعم ملفات Office و OCR
RUN apt-get update && apt-get install -y \
    build-essential \
    libmagic1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    tesseract-ocr \
    poppler-utils \
    libreoffice \
    curl \
    && apt-get clean

# إعداد مجلد التطبيق
WORKDIR /app

# نسخ ملفات المشروع إلى الحاوية
COPY . .

# تثبيت المكتبات من requirements.txt
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# إعداد الأوامر التي تشغل التطبيق
CMD ["gunicorn", "backend.wsgi:application", "--bind", "0.0.0.0:10000"]
