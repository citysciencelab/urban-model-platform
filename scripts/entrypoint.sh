#!/bin/bash
set -e

echo "Running API Server in production mode."
NUMBER_OF_WORKERS="${NUMBER_OF_WORKERS:-1}"
echo "Running gunicorn with ${NUMBER_OF_WORKERS} workers."
# export PATH=$PATH:/home/python/.local/bin
exec gunicorn --workers=$NUMBER_OF_WORKERS --bind=0.0.0.0:5000 ump.main:app
