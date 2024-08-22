#!/bin/bash
set -e

if [ -z "$CORS_URL_REGEX" ]; then
  echo "ERROR: Environment variable CORS_URL_REGEX is not configured."
  exit 1
fi

echo "Running API Server in production mode."
NUMBER_OF_WORKERS="${NUMBER_OF_WORKERS:-1}"
echo "Running gunicorn with ${NUMBER_OF_WORKERS} workers."
# export PATH=$PATH:/home/python/.local/bin
exec gunicorn --workers=$NUMBER_OF_WORKERS --bind=0.0.0.0:5000 ump.main:app

