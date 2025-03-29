(Keycloak)=
# Keycloak

 Keycloak is an open-source Identity and Access Management (IAM) solution that provides user authentication, authorization, and single sign-on capabilities. It enables secure access to applications and services by managing user identities and permissions. In the Urban Model Platform, Keycloak serves as the central authentication server, handling access control across components.

## Configure Keycloak
1. Open Keycloak on `http://localhost:${KEYCLOAK_PORT_EXTERNAL}/auth`
2. In order to configure a dev setup Keycloak initially, log in with admin/admin. Then:
3. Create a new realm named `UrbanModelPlatform`
4. Create a new client in that realm called `ump-client` (activate OAuth 2.0 Device Authorization Grant and Direct access grants)
5. Create a test user called `ump`, set its password to `ump`
6. Make sure to set the keycloak host in `.env` to your local hostname or IP address

## Securing Model Servers and Processes

You can secure processes and model servers in keycloak by adding users to special client roles. In order to secure a specific process, create a role named `modelserver_processid`, in order to secure all processes of a model server just create a role named `modelserver`. The ids correspond to the keys used in the providers.yaml.


## Accessing secured Processes in Development

If you access the `/processes` list without any authentification, you can see all processes which are configured to be `anonymous_access: True` (Learn more about the configuration of providers [here](providers)). If you want to see all processes a specific user is authorized to see, follow the following steps:

1. Log in with admin/admin
2. Go to the user (e.g. `ump`) and make sure to fill out the general information and switch on "E-Mail verified"
3. Log out and log in to the user `ump` via the following URL: `http://localhost:${KEYCLOAK_PORT_EXTERNAL}/auth/realms/UrbanModelPlatform/account`
4. Obtain the client secret by going to the client, clicking `Credentials` and copying the secret
5. If the login is working, get token for user:

```bash
curl -X POST "http://localhost:${KEYCLOAK_PORT_EXTERNAL}/auth/realms/UrbanModelPlatform/protocol/openid-connect/token" \
-H "Content-Type: application/x-www-form-urlencoded" \
-d "grant_type=password" \
-d "client_id=ump-client" \
-d "client_secret=<client-secret>" \
-d "username=ump" \
-d "password=ump"
```

6. With the token obtained, you can access the entire processes list by executing:
```bash
curl -L -v -X GET "http://localhost:<WEBAPP_PORT_EXTERNAL>/api/processes" \
-H -H "Authorization: Bearer <insert_token_here>"
```