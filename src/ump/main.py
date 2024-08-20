import json
import os
from logging.config import dictConfig

from apiflask import APIBlueprint, APIFlask
from flask import jsonify
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from ump.api.routes.jobs import jobs
from ump.api.routes.processes import processes
from ump.errors import CustomException

if (
    # The WERKZEUG_RUN_MAIN is set to true when running the subprocess for
    # reloading, we want to start debugpy only once during the first
    # invocation and never during reloads.
    # See https://github.com/microsoft/debugpy/issues/1296#issuecomment-2012778330
    os.environ.get("WERKZEUG_RUN_MAIN") != "true" and os.environ.get('FLASK_DEBUG') == '1'
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

app.config["DEBUG"] = os.environ.get("FLASK_DEBUG", 0)

CORS(app)

api = APIBlueprint("api", __name__, url_prefix="/api")
api.register_blueprint(processes, url_prefix="/processes")
api.register_blueprint(jobs, url_prefix="/jobs")

app.register_blueprint(api)

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
    app.run(host="0.0.0.0", port=5001, debug=False)
