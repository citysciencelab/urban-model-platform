#TODO: this file has become a hodgepodge of very different things,
# it should be split into dedicated files:
# - an app factory for migrations
# - logging setup
# - a geoserver cleanup runner
# - the flask app 
import atexit
import json
import os
from datetime import datetime, timedelta
from logging.config import dictConfig

import requests
import schedule
from apiflask import APIBlueprint, APIFlask
from flask import g, jsonify, request
from flask_cors import CORS
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from keycloak import KeycloakOpenID, KeycloakGetError, KeycloakConnectionError
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

from ump.api.db_handler import DBHandler, close_pool
from ump.api.providers import PROVIDERS
from ump.api.routes.ensembles import ensembles
from ump.api.routes.health import health_bp
from ump.api.routes.jobs import jobs
from ump.api.routes.processes import processes
from ump.api.routes.users import users
from ump.config import app_settings as config
from ump.errors import CustomException

dictConfig(
    {
        "version": 1,
        "formatters": {
            "default": {
                "format": "[%(asctime)s] %(levelname)s in %(module)s: %(message)s",
            }
        },
        "handlers": {
            "wsgi": {
                "class": "logging.StreamHandler",
                "stream": "ext://flask.logging.wsgi_errors_stream",
                "formatter": "default",
            }
        },
        "root": {
            "level": config.UMP_LOG_LEVEL,
            "handlers": ["wsgi"]
        },
        "loggers": {
            "ump.api.providers": {  # Configure the logger for providers.py
                "level": config.UMP_LOG_LEVEL,
                "handlers": ["wsgi"],
                "propagate": False,  # Prevent duplicate logging
            },
            "ump.api.processes": {  # Configure the logger for processes.py
                "level": config.UMP_LOG_LEVEL,
                "handlers": ["wsgi"],
                "propagate": False,
            },
        },
    }
)


def cleanup():
    """Cleans up jobs and Geoserver layers of anonymous users"""
    sql = "delete from jobs where user_id is null and finished < %(finished)s returning job_id, provider_prefix, process_id"
    finished = datetime.now() - timedelta(minutes = config.UMP_JOB_DELETE_INTERVAL)
    
    with DBHandler() as conn:
        result = conn.run_query(sql, query_params={'finished': finished})
        for row in result:
            # get additional job metadata
            job_id, provider_prefix, process_id = row

            # Check if result-storage is set to geoserver
            result_storage = (
                PROVIDERS.get(provider_prefix, {})
                .get("processes", {})
                .get(process_id, {})
                .get("result-storage", None)
            )
            if result_storage == "geoserver":
                requests.delete(
                    f"{config.UMP_GEOSERVER_URL_WORKSPACE}/{config.UMP_GEOSERVER_WORKSPACE_NAME}"
                    + f"/layers/{job_id}.xml",
                    auth=(
                        config.UMP_GEOSERVER_USER,
                        config.UMP_GEOSERVER_PASSWORD.get_secret_value
                    ),
                    timeout=config.UMP_GEOSERVER_CONNECTION_TIMEOUT,
                )
                requests.delete(
                    f"{config.UMP_GEOSERVER_URL_WORKSPACE}/{config.UMP_GEOSERVER_WORKSPACE_NAME}"
                    + f"/datastores/{job_id}/featuretypes/{job_id}.xml",
                    auth=(config.UMP_GEOSERVER_USER, config.UMP_GEOSERVER_PASSWORD.get_secret_value()),
                    timeout=config.UMP_GEOSERVER_CONNECTION_TIMEOUT,
                )
                requests.delete(
                    f"{config.UMP_GEOSERVER_URL_WORKSPACE}/{config.UMP_GEOSERVER_WORKSPACE_NAME}"
                    + f"/datastores/{job_id}.xml",
                    auth=(config.UMP_GEOSERVER_USER, config.UMP_GEOSERVER_PASSWORD.get_secret_value()),
                    timeout=config.UMP_GEOSERVER_CONNECTION_TIMEOUT,
                )


# TODO: this is NOT good for production environments!
# cleanup is a different task and should NOT be part of
# the main app, instead it should be outsourced to a module and should be optionally
# I suggest to use celery and redis for this task
# also it does not work, cleanup is called when the routes are accessed, not on a regular basis
schedule.every(int(config.UMP_JOB_DELETE_INTERVAL)).seconds.do(cleanup)

app = APIFlask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

app.config["DEBUG"] = os.environ.get("FLASK_DEBUG", 0)
app.config["SQLALCHEMY_DATABASE_URI"] = (
    f"postgresql+psycopg2://{config.UMP_DATABASE_USER}:{config.UMP_DATABASE_PASSWORD.get_secret_value()}"
    + f"@{config.UMP_DATABASE_HOST}:{config.UMP_DATABASE_PORT}/{config.UMP_DATABASE_NAME}"
)

db = SQLAlchemy(app)
migrate = Migrate(app, db)

CORS(app)

api = APIBlueprint("api", __name__, url_prefix=config.UMP_URL_PREFIX)
api.register_blueprint(processes, url_prefix="/processes")
api.register_blueprint(jobs, url_prefix="/jobs")
api.register_blueprint(ensembles, url_prefix="/ensembles")
api.register_blueprint(users, url_prefix="/users")
api.register_blueprint(health_bp, url_prefix="/health")

app.register_blueprint(api)

# this does not check the connection yet, so app can fail later on!

keycloak_openid = KeycloakOpenID(
    server_url=str(config.UMP_KEYCLOAK_URL),
    client_id=config.UMP_KEYCLOAK_CLIENT_ID,
    realm_name=config.UMP_KEYCLOAK_REALM,
)

@app.before_request
def check_jwt():
    """Decodes the JWT token and runs pending scheduled jobs"""
    # TODO: this is senseless, too
    schedule.run_pending()
    auth = request.authorization

    if auth is not None:
        # need exception handling here to avoid app failure!
        try:
            # TODO: generally token verification is done offline,
            # but decode_token connects to keycloak on every request (for retrieving keys)
            decoded = keycloak_openid.decode_token(auth.token)
        except KeycloakGetError as e:
            app.logger.error(e)
            raise CustomException(
                message="Keycloak: Resource not found. Check Keycloak URL path.",
                status_code=404,
            )
        except KeycloakConnectionError as e:
            app.logger.error(e)
            raise CustomException(
                message="Keycloak: Connection error. Check Keycloak URL host.",
                status_code=500,
            )
        except Exception as e:
            app.logger.error(e)
            raise CustomException(
                message="Keycloak: Unknown error. Check Keycloak URL.",
                status_code=500,
            )
        g.auth_token = decoded
    else:
        g.auth_token = None
    pass

@app.after_request
def set_headers(response):
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.errorhandler(CustomException)
def handle_invalid_usage(error):
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response


@app.errorhandler(HTTPException)
def handle_http_exception(error):
    """Return JSON instead of HTML for HTTP errors."""
    # start with the correct headers and status code from the error
    response = error.get_response()
    # replace the body with JSON
    response.data = json.dumps(
        {
            "code": error.code,
            "name": error.name,
            "description": error.description,
        }
    )
    response.content_type = "application/json"
    return response


@atexit.register
def shutdown_pool_on_exit():
    """Close the connection pool when the application shuts down."""
    close_pool()

if __name__ == "__main__":
    app.run(host="0.0.0.0")
