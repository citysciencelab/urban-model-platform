# Keycloak

 Keycloak is an open-source Identity and Access Management (IAM) solution that provides user authentication, authorization, and single sign-on capabilities. It enables secure access to applications and services by managing user identities and permissions. In the Urban Model Platform, Keycloak serves as the central authentication server, handling access control across components.

# Configure keycloak

* Open Keycloak on localhost:${KEYCLOAK_PORT_EXTERNAL}/auth

* In order to configure a dev setup Keycloak initially, log in with admin/admin. Then:

* create a new realm named `UrbanModelPlatform`

* create a new client in that realm called `ump-client` (activate OAuth 2.0 Device Authorization Grant and Direct access grants)

* create a test user called `ump`, set its password to `ump`

* make sure to set the keycloak host in `.env` to your local hostname or IP address

* You can secure processes and model servers in keycloak by adding users to special client roles. In order to secure a specific process, create a client role named `modelserver_processid`, in order to secure all processes of a model server just create a role named `modelserver`. The ids correspond to the keys used in the providers.yaml.

 

* If you open the /processes list without logging in, you can see all processes which have an "anonymous_access". If you want to see all processes you are authorized to see, do the following steps:

    * log in with admin/admin

    * go to user (f.e. ump) and make sure to fill out the general information and switch on "E-Mail verified"

    * log out and log in to the user ump via following URL: http://localhost:${KEYCLOAK_PORT_EXTERNAL}/auth/realms/UrbanModelPlatform/account

    Within the normal admin page, get the client secret of ump-client for the curl below

    * if the login is working, get token for user:

        curl -X POST "http://localhost:${KEYCLOAK_PORT_EXTERNAL}/auth/realms/UrbanModelPlatform/protocol/openid-connect/token" \

        -H "Content-Type: application/x-www-form-urlencoded" \

        -d "grant_type=password" \

        -d "client_id=ump-client" \

        -d "client_secret=<client-secret>" \

        -d "username=ump" \

        -d "password=ump"

        * to get the client secret, go to the client, click credentials and copy the secret

        * the result is the token, use it to get the entire processes-list

    * in order to get the list, do:

        curl -L -v -X GET "http://localhost:<WEBAPP_PORT_EXTERNAL>/api/processes" \

        -H "Authorization: Bearer <insert_token_here>"