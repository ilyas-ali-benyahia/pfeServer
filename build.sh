#!/usr/bin/env bash

# Update system packages and install dependencies
apt-get update && apt-get install -y \
  tesseract-ocr \
  libmagic1 \
  libxml2 \
  libxslt1-dev
