"""Keycloak helper functions"""
from os import environ as env

from keycloak import KeycloakAdmin, KeycloakOpenIDConnection

keycloak_connection = KeycloakOpenIDConnection(
    server_url=f"{env['KEYCLOAK_PROTOCOL']}://{env['KEYCLOAK_HOST']}/auth/",
    username=env["KEYCLOAK_USER"],
    password=env["KEYCLOAK_PASSWORD"],
    realm_name="master",
    user_realm_name="master",
    client_id="admin-cli",
    verify=True,
)

keycloak_admin = KeycloakAdmin(connection=keycloak_connection)
keycloak_admin.change_current_realm("UrbanModelPlatform")


def find_user_id_by_email(email):
    """Retrieves a user id by email"""
    users = keycloak_admin.get_users({"email": email})
    for user in users:
        if user["email"] == email:
            return user["id"]
    return None


def get_user_name(user_id):
    """Retrieve the username by user id"""
    user = keycloak_admin.get_user(user_id)
    return user["username"] if user else None
