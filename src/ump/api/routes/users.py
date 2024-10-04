import json
from os import environ as env

import requests
from apiflask import APIBlueprint
from flask import Response, g, request
from keycloak import KeycloakAdmin

users = APIBlueprint("users", __name__)


def getToken():
    token_url = f"{env['KEYCLOAK_PROTOCOL']}://{env['KEYCLOAK_HOST']}/auth/realms/master/protocol/openid-connect/token"

    data = {
        "grant_type": "password",
        "client_id": "admin-cli",
        "username": env["KEYCLOAK_USER"],
        "password": env["KEYCLOAK_PASSWORD"],
    }

    response = requests.post(token_url, data=data)
    if response.status_code != 200:
        print("Fehler beim Abrufen des Tokens:", response.text)
        exit()

    token_info = response.json()
    access_token = token_info["access_token"]

    return access_token


@users.route("/<path:user_id>/name")
def index(user_id=None):
    auth = g.get("auth_token")
    if auth is None:
        return Response(mimetype="application/json", status=401)

    access_token = getToken()
    user_url = f"{env['KEYCLOAK_PROTOCOL']}://{env['KEYCLOAK_HOST']}/auth/admin/realms/UrbanModelPlatform/users/{user_id}"

    headers = {
        "Authorization": f"Bearer {access_token}",
    }

    user_response = requests.get(user_url, headers=headers)
    if user_response.status_code != 200:
        return Response(mimetype="application/json", status=404)

    user_info = user_response.json()
    user_name = user_info.get("username")
    response_data = {
        "user_id": user_id,
        "username": user_name,
    }

    return Response(json.dumps(response_data), mimetype="application/json")
