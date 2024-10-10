import json

from apiflask import APIBlueprint
from flask import Response, g

from ump.api.keycloak import get_user_name

users = APIBlueprint("users", __name__)


@users.route("/<path:user_id>/name")
def index(user_id=None):
    auth = g.get("auth_token")
    if auth is None:
        return Response(mimetype="application/json", status=401)

    user_name = get_user_name(user_id)
    response_data = {
        "user_id": user_id,
        "username": user_name,
    }

    return Response(json.dumps(response_data), mimetype="application/json")
