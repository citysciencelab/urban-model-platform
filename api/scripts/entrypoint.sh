#!/bin/bash
set -e

if [ -z "$CORS_URL_REGEX" ]; then
  echo "ERROR: Environment variable CORS_URL_REGEX is not configured."
  exit 1
fi

if [ $FLASK_DEBUG == 1 ]; then
  echo "Running API Server in debug mode."
  python main.py
else
  echo "Running API Server in production mode."
  NUMBER_OF_WORKERS="${NUMBER_OF_WORKERS:-1}"
  echo "Running gunicorn with ${NUMBER_OF_WORKERS} workers."
  export PATH=$PATH:/home/python/.local/bin
  gunicorn --workers=$NUMBER_OF_WORKERS --bind=0.0.0.0:5001 main:app
fi
