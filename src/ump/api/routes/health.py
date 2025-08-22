import logging
import time
from datetime import datetime
from pathlib import Path

import psycopg2
import requests
from flask import Blueprint, jsonify
from sqlalchemy import text

from ump.api.db_handler import DBHandler, db_engine
from ump.config import app_settings as config

logger = logging.getLogger(__name__)
health_bp = Blueprint('health', __name__)

def check_database():
    """Check database connectivity and basic operations."""
    try:
        start_time = time.time()
        with DBHandler() as db:
            # Test basic query
            result = db.run_query("SELECT 1 as test, NOW() as timestamp")
            response_time = round((time.time() - start_time) * 1000, 2)
            
            return {
                "status": "healthy",
                "response_time_ms": response_time,
                "timestamp": result[0]["timestamp"].isoformat() if result else None
            }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "response_time_ms": None
        }

def check_geoserver_database():
    """Check GeoServer database connectivity."""
    try:
        start_time = time.time()
        connection = psycopg2.connect(
            host=config.UMP_GEOSERVER_DB_HOST,
            port=config.UMP_GEOSERVER_DB_PORT,
            database=config.UMP_GEOSERVER_DB_NAME,
            user=config.UMP_GEOSERVER_DB_USER,
            password=config.UMP_GEOSERVER_DB_PASSWORD.get_secret_value()
        )
        cursor = connection.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        response_time = round((time.time() - start_time) * 1000, 2)
        
        cursor.close()
        connection.close()
        
        return {
            "status": "healthy",
            "response_time_ms": response_time
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "response_time_ms": None
        }

def check_geoserver():
    """Check GeoServer REST API connectivity."""
    if not config.UMP_GEOSERVER_URL:
        return {
            "status": "disabled",
            "message": "GeoServer URL not configured"
        }
    
    try:
        start_time = time.time()
        url = f"{config.UMP_GEOSERVER_URL_REST}/about/version"
        response = requests.get(
            url,
            auth=(config.UMP_GEOSERVER_USER, config.UMP_GEOSERVER_PASSWORD.get_secret_value()),
            timeout=config.UMP_GEOSERVER_CONNECTION_TIMEOUT
        )
        response_time = round((time.time() - start_time) * 1000, 2)
        
        if response.status_code == 200:
            return {
                "status": "healthy",
                "response_time_ms": response_time,
                "version_info": response.text[:200] if response.text else None
            }
        else:
            return {
                "status": "unhealthy",
                "error": f"HTTP {response.status_code}",
                "response_time_ms": response_time
            }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "response_time_ms": None
        }

def check_keycloak():
    """Check Keycloak connectivity."""
    try:
        start_time = time.time()
        # Check Keycloak realm endpoint
        url = f"{config.UMP_KEYCLOAK_URL}/realms/{config.UMP_KEYCLOAK_REALM}"
        response = requests.get(url, timeout=30)
        response_time = round((time.time() - start_time) * 1000, 2)
        
        if response.status_code == 200:
            realm_info = response.json()
            return {
                "status": "healthy",
                "response_time_ms": response_time,
                "realm": realm_info.get("realm"),
                "display_name": realm_info.get("displayName")
            }
        else:
            return {
                "status": "unhealthy",
                "error": f"HTTP {response.status_code}",
                "response_time_ms": response_time
            }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "response_time_ms": None
        }

def check_providers_config():
    """Check if providers configuration file exists and is readable."""
    try:
        providers_file = Path(config.UMP_PROVIDERS_FILE)
        if not providers_file.exists():
            return {
                "status": "unhealthy",
                "error": f"Providers file not found: {providers_file}"
            }
        
        if not providers_file.is_file():
            return {
                "status": "unhealthy",
                "error": f"Providers path is not a file: {providers_file}"
            }
        
        # Check if file is readable and get basic info
        file_size = providers_file.stat().st_size
        modified_time = datetime.fromtimestamp(providers_file.stat().st_mtime)
        
        return {
            "status": "healthy",
            "file_path": str(providers_file),
            "file_size_bytes": file_size,
            "last_modified": modified_time.isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }

@health_bp.route('/')
def health_check():
    """Comprehensive health check endpoint."""
    start_time = time.time()
    
    # Perform all health checks
    checks = {
        "database": check_database(),
        "geoserver_database": check_geoserver_database(),
        "geoserver": check_geoserver(),
        "keycloak": check_keycloak(),
        "providers_config": check_providers_config()
    }
    
    # Determine overall status
    overall_status = "healthy"
    for check_name, check_result in checks.items():
        if check_result.get("status") in ["unhealthy"]:
            overall_status = "unhealthy"
            break
        elif check_result.get("status") in ["degraded"]:
            overall_status = "degraded"
    
    total_response_time = round((time.time() - start_time) * 1000, 2)
    
    response_data = {
        "status": overall_status,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "total_response_time_ms": total_response_time,
        "checks": checks,
        "version": {
            "app": "Urban Model Platform",
            "python": f"{config.UMP_DATABASE_HOST}:{config.UMP_DATABASE_PORT}"
        }
    }
    
    # Set appropriate HTTP status code
    status_code = 200 if overall_status == "healthy" else 503 if overall_status == "unhealthy" else 200
    
    return jsonify(response_data), status_code

@health_bp.route('/ready')
def readiness():
    """Simple readiness probe - checks only critical dependencies."""
    try:
        # Check database connectivity (critical)
        db_check = check_database()
        if db_check["status"] != "healthy":
            return jsonify({
                "status": "not_ready",
                "reason": "database_unavailable",
                "details": db_check
            }), 503
        
        # Check providers config exists (critical)
        config_check = check_providers_config()
        if config_check["status"] != "healthy":
            return jsonify({
                "status": "not_ready", 
                "reason": "providers_config_unavailable",
                "details": config_check
            }), 503
        
        return jsonify({
            "status": "ready",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }), 200
        
    except Exception as e:
        logger.exception("Readiness check failed")
        return jsonify({
            "status": "not_ready",
            "reason": "internal_error",
            "error": str(e)
        }), 503

@health_bp.route('/live')
def liveness():
    """Simple liveness probe - basic application health."""
    return jsonify({
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }), 200