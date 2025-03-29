(docker-configuration)=
# Configuration of the Docker Environment


## Environment Variables
...to be configured in the .env file in the root directory of this project. Below you can find a list of all environment variables and their example values, as also shown in the `.env.example` file.


| Variable Name                  | Description                                                                                       | Example Value                      |
|--------------------------------|---------------------------------------------------------------------------------------------------|------------------------------------|
| `WEBAPP_PORT_EXTERNAL`         | The external port for the web application                                                         | `5003`                             |
| `API_SERVER_URL`               | The base URL to the API, used to return the complete URL in the result of job details as specified in OGC | `http://localhost`                 |
| `NUMBER_OF_WORKERS`            | The number of workers                                                                             | `1`                                |
| `LOGLEVEL`                     | The log level for the application                                                                 | `DEBUG`                            |
| `FLASK_DEBUG`                  | Enable or disable Flask debug mode                                                                | `1`                                |
| `PROVIDERS_FILE`               | The file name for providers configuration                                                         | `providers.yaml`                   |
| `GEOSERVER_WORKSPACE`          | The workspace name in GeoServer                                                                   | `CUT`                              |
| `GEOSERVER_ADMIN_USER`         | The admin username for GeoServer                                                                  | `admin`                            |
| `GEOSERVER_ADMIN_PASSWORD`     | The admin password for GeoServer                                                                  | `geoserver`                        |
| `GEOSERVER_BASE_URL`           | The base URL for GeoServer                                                                        | `geoserver:8080/geoserver`         |
| `GEOSERVER_PORT`               | The internal port for GeoServer                                                                   | `8080`                             |
| `GEOSERVER_POSTGIS_HOST`       | The host for PostGIS used by GeoServer                                                            | `postgis`                          |
| `GEOSERVER_PORT_EXTERNAL`      | The external port for GeoServer                                                                   | `8080`                             |
| `GEOSERVER_TIMEOUT`            | The timeout value for GeoServer operations (in seconds)                                           | `60`                               |
| `CLEANUP_AGE`                  | The cleanup age for temporary resources (in minutes)                                              | `240`                              |
| `POSTGRES_DB`                  | The name of the PostgreSQL/PostGIS database                                                       | `cut_dev`                          |
| `POSTGRES_USER`                | The username for PostgreSQL/PostGIS                                                               | `postgres`                         |
| `POSTGRES_PASSWORD`            | The password for PostgreSQL/PostGIS                                                               | `postgres`                         |
| `POSTGRES_HOST`                | The host for PostgreSQL/PostGIS                                                                   | `postgis`                          |
| `POSTGRES_PORT`                | The port for PostgreSQL/PostGIS                                                                   | `5432`                             |
| `PYGEOAPI_CONFIG`              | The file path for the PyGeoAPI configuration                                                      | `/home/pythonuser/pygeoapi-config.yaml` |
| `PYGEOAPI_OPENAPI`             | The file path for the PyGeoAPI OpenAPI specification                                              | `/home/pythonuser/pygeoapi-openapi.yaml` |
| `PYGEOAPI_SERVER_HOST`         | The host for the PyGeoAPI server                                                                  | `localhost`                        |
| `PYGEOAPI_SERVER_PORT_INTERNAL`| The internal port for the PyGeoAPI server                                                         | `5000`                             |
| `PYGEOAPI_SERVER_PORT_EXTERNAL`| The external port for the PyGeoAPI server                                                         | `5005`                             |
| `KEYCLOAK_USER`                | The admin username for Keycloak                                                                   | `admin`                            |
| `KEYCLOAK_PASSWORD`            | The admin password for Keycloak                                                                   | `admin`                            |
| `KEYCLOAK_HOST`                | The host for Keycloak                                                                             | `localhost`                        |
| `KEYCLOAK_PROTOCOL`            | The protocol for Keycloak (http or https)                                                         | `http`                             |
| `KEYCLOAK_PORT_EXTERNAL`       | The external port for Keycloak                                                                    | `8081`                             |
| `KC_KEYCLOAK_HOST`             | The Keycloak host for internal services                                                           | `localhost`                        |
| `DOCKER_NETWORK`               | The Docker network for the development environment                                                | `dev`                              |
| `CONTAINER_REGISTRY`           | The container registry URL                                                                        | `registry.io`                      |
| `CONTAINER_NAMESPACE`          | The container namespace                                                                           | `namespace`                        |
| `IMAGE_NAME`                   | The name of the Docker image                                                                      | `urban-model-platform`             |
| `IMAGE_TAG`                    | The tag for the Docker image                                                                      | `1.1.0`                            |
