#!/bin/bash
set -e

flask db upgrade

echo "Running API Server in production mode."
UMP_API_SERVER_WORKERS="${UMP_API_SERVER_WORKERS:-1}"
echo "Running gunicorn with ${UMP_API_SERVER_WORKERS} workers."
# export PATH=$PATH:/home/python/.local/bin
exec gunicorn --workers=$UMP_API_SERVER_WORKERS --bind=0.0.0.0:5000 ump.main:app
