import json
import os
from datetime import datetime, timedelta
from logging.config import dictConfig
from os import environ as env

import requests
import schedule
from apiflask import APIBlueprint, APIFlask
from flask import g, jsonify, request
from flask_cors import CORS
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from keycloak import KeycloakOpenID
from sqlalchemy import create_engine
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

from ump import config
from ump.api.routes.ensembles import ensembles
from ump.api.routes.jobs import jobs
from ump.api.routes.processes import processes
from ump.api.routes.users import users
from ump.config import CLEANUP_AGE
from ump.errors import CustomException
from ump.api.providers import PROVIDERS

if (
    # The WERKZEUG_RUN_MAIN is set to true when running the subprocess for
    # reloading, we want to start debugpy only once during the first
    # invocation and never during reloads.
    # See https://github.com/microsoft/debugpy/issues/1296#issuecomment-2012778330
    os.environ.get("WERKZEUG_RUN_MAIN") != "true"
    and os.environ.get("FLASK_DEBUG") == "1"
):
    import debugpy

    debugpy.listen(("0.0.0.0", 5678))

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
        "root": {"level": os.environ.get("LOGLEVEL", "WARNING"), "handlers": ["wsgi"]},
    }
)

def cleanup():
    """Cleans up jobs and Geoserver layers of anonymous users"""
    engine = create_engine(f"postgresql+psycopg2://{config.postgres_user}:{config.postgres_password}"+f"@{config.postgres_host}:{config.postgres_port}/{config.postgres_db}")    
    sql = "delete from jobs where user_id is null and finished < %(finished)s returning job_id, provider_prefix, process_id"
    finished = datetime.now() - timedelta(minutes = CLEANUP_AGE)
    with engine.begin() as conn:
        result = conn.exec_driver_sql(sql, {'finished': finished})
        for row in result:
            # get additional job metadata
            job_id, provider_prefix, process_id = row

            # Check if result-storage is set to geoserver
            result_storage = PROVIDERS.get(provider_prefix, {}).get('processes', {}).get(process_id, {}).get('result-storage', None)
            if result_storage == "geoserver":
                requests.delete(
                    f"{config.geoserver_workspaces_url}/{config.geoserver_workspace}" +
                        f"/layers/{job_id}.xml",
                    auth=(config.geoserver_admin_user, config.geoserver_admin_password),
                    timeout=config.GEOSERVER_TIMEOUT,
                )
                requests.delete(
                    f"{config.geoserver_workspaces_url}/{config.geoserver_workspace}" +
                        f"/datastores/{job_id}/featuretypes/{job_id}.xml",
                    auth=(config.geoserver_admin_user, config.geoserver_admin_password),
                    timeout=config.GEOSERVER_TIMEOUT,
                )
                requests.delete(
                    f"{config.geoserver_workspaces_url}/{config.geoserver_workspace}" +
                        f"/datastores/{job_id}.xml",
                    auth=(config.geoserver_admin_user, config.geoserver_admin_password),
                    timeout=config.GEOSERVER_TIMEOUT,
                )


schedule.every(60).seconds.do(cleanup)

app = APIFlask(__name__)
app.wsgi_app = ProxyFix(
    app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1
)

app.config["DEBUG"] = os.environ.get("FLASK_DEBUG", 0)
app.config["SQLALCHEMY_DATABASE_URI"] = (f"postgresql+psycopg2://{config.postgres_user}:{config.postgres_password}"+f"@{config.postgres_host}:{config.postgres_port}/{config.postgres_db}")

db = SQLAlchemy(app)
migrate = Migrate(app, db)

CORS(app)

api = APIBlueprint("api", __name__, url_prefix="/api")
api.register_blueprint(processes, url_prefix="/processes")
api.register_blueprint(jobs, url_prefix="/jobs")
api.register_blueprint(ensembles, url_prefix="/ensembles")
api.register_blueprint(users, url_prefix="/users")

app.register_blueprint(api)

keycloak_openid = KeycloakOpenID(
    server_url=f"{env['KEYCLOAK_PROTOCOL']}://{env['KEYCLOAK_HOST']}/auth/",
    client_id="ump-client",
    realm_name="UrbanModelPlatform",
)


@app.before_request
def check_jwt():
    """Decodes the JWT token and runs pending scheduled jobs"""
    schedule.run_pending()
    auth = request.authorization
    if auth is not None:
        decoded = keycloak_openid.decode_token(auth.token)
        g.auth_token = decoded
    else:
        g.auth_token = None


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


if __name__ == "__main__":
    app.run(host="0.0.0.0")
