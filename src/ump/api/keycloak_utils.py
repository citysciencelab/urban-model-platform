"""Keycloak helper functions"""

from keycloak import KeycloakAdmin, KeycloakOpenIDConnection

from ump.config import app_settings as config

keycloak_connection = KeycloakOpenIDConnection(
    server_url=str(config.UMP_KEYCLOAK_URL),
    username=f"{config.UMP_KEYCLOAK_USER}",
    password=f"{config.UMP_KEYCLOAK_PASSWORD.get_secret_value()}",
    realm_name="master",
    user_realm_name="master",
    client_id="admin-cli",
    verify=True,
)

keycloak_admin = KeycloakAdmin(connection=keycloak_connection)
keycloak_admin.change_current_realm(f"{config.UMP_KEYCLOAK_REALM}")


def find_user_id_by_email(email):
    """Retrieves a user id by email"""
    users = keycloak_admin.get_users({"email": email})
    for user in users:
        if user["email"] == email:
            return user["id"]
    return None


def get_user_details(user_id):
    """Retrieve the user details by user id"""
    user = keycloak_admin.get_user(user_id)
    return user
