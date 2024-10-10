"""Endpoints to access user information via keycloak"""

import json

from apiflask import APIBlueprint
from flask import Response, g

from ump.api.keycloak_utils import get_gravatar_url, get_user_name

users = APIBlueprint("users", __name__)


@users.route("/<path:user_id>/details", methods=["GET"])
def index(user_id=None):
    "Retrieve user name by user id"
    auth = g.get("auth_token")
    if auth is None:
        return Response(mimetype="application/json", status=401)

    user_name = get_user_name(user_id)
    gravatar_url = get_gravatar_url(user_id)

    response_data = {
        "user_id": user_id,
        "username": user_name,
        "gravatar_url": gravatar_url,
    }

    return Response(json.dumps(response_data), mimetype="application/json")
