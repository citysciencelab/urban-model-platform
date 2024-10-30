import json
import os
from logging.config import dictConfig
from os import environ as env

from apiflask import APIBlueprint, APIFlask
from flask import g, jsonify, request
from flask_cors import CORS
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from keycloak import KeycloakOpenID
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

from ump.api.routes.ensembles import ensembles
from ump.api.routes.jobs import jobs
from ump.api.routes.processes import processes
from ump.api.routes.users import users
from ump.errors import CustomException

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

app = APIFlask(__name__)
app.wsgi_app = ProxyFix(
    app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1
)

app.config["DEBUG"] = os.environ.get("FLASK_DEBUG", 0)
app.config["SQLALCHEMY_DATABASE_URI"] = (
    "postgresql+psycopg2://postgres:postgres@postgis/cut_dev"
)

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
