# Use an official Python image as a base
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libmagic1 \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy the project files into the container
COPY . .

# Install Python dependencies
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Expose port 8000 for the Django application
EXPOSE 8000

# Run the application with Gunicorn (replace 'your_project_name' with your actual project name)
CMD ["gunicorn", "backend.wsgi:application", "--bind", "0.0.0.0:8000"]
