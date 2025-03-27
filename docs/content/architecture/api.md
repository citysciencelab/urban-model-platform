# OGC Processes API

## API documentation
This API implements the OGC processes standard (except that it is not complete). E.g. there is no html landingpage implemented, only the API.

For an API description e.g. for the jobs list see:
https://docs.ogc.org/is/18-062r2/18-062r2.html#rc_job-list
or
https://developer.ogc.org/api/processes/index.html#tag/JobList

For convenience there is still some documentation below.

## Setup
Also the list of providers delivering the OGC API Processes  have to be configured in [providers.yaml](../../../providers.yaml.example) along with the processes that the UMP should provide. The structure looks as following:

```
modelserver-1:
    url: "http://localhost:5005"
    name: "CSL Test Modelserver"
    authentication:
      type: "BasicAuth"
      user: "user"
      password: "password"
    timeout:  60
    processes:
      process-1:
        result-storage: "geoserver"
        result-path: simulation_geometry
        graph-properties:
          root-path: results.simulation_results
        anonymous-access: True
      process-2
        result-storage: "remote"
        deterministic: True
      process-3
        exclude: True
```

For each process, it is possible to choose from result-storage options. If the attribute `result-storage` is set to `remote`, no results will be stored in the UMP itself, but provided directly from the model server. In case it is set to `geoserver`, UMP will load the geoserver component and tries to store the result data in a specific Geoserver layer. You can specify the object path to the feature collection using `result-path`. Use dots to separate a path with several components: `result-path: result.some_obj.some_features`.

Processes configured with `anonymous-access: True` can be seen and run by anonymous users. Jobs and layers created by anonymous users will be cleaned up after some time (this can be configured in `config.py`).

Processes can be configured with `deterministic: True`. If so, jobs will be cached based on a hash of the input parameters, the process version and the user id.

With `graph-properties` and the sub-properties `root-path`, `x-path` and `y-path` you can configure processes to simplify graph configuration in the UI.

## Keycloak

You can secure processes and model servers in keycloak by adding users to special client roles. In order to secure a specific process, create a role named `modelserver_processid`, in order to secure all processes of a model server just create a role named `modelserver`. The ids correspond to the keys used in the providers.yaml.


### GET api/jobs
Example parameters:
```
?limit=1&page=1&status=running&status=successful
```

Default limit: none.
Parameters are optional.

## Access DB
We have two DB users:
- the privileged POSTGRES_USER user configured in .env file
- the user used by the API with privileges on the jobs table (e.g. see api/initializers/db/create_db_user.sh). Its credentials are configured in docker-compose.yml.

```
docker-compose exec postgis bash
psql -U <username> -d <db_name>
```

## Environment Variables
...to be configured in the .env file in the root directory of this project. You can use the .env.example file as a template.

| Variable                         | Example Value                  | Description |
|----------------------------------|--------------------------------|-------------|
| `WEBAPP_PORT_EXTERNAL`           | `5003`                         | External port for the web application. |
| `API_SERVER_URL`                 | `http://localhost`             | # The API_SERVER_URL is only used to return the complete URL in the result of the job details as specified in OGC. Should be the base url to the api. |
| `NUMBER_OF_WORKERS`              | `1`                            | Number of worker threads for gunicorn. |
| `LOGLEVEL`                       | `DEBUG`                        | Logging level (e.g., DEBUG, INFO, ERROR). |
| `FLASK_DEBUG`                    | `1`                            | Enables Flask debugging mode (1 = enabled). |
| `PROVIDERS_FILE`                 | `/app/providers.yaml`          | Path to the providers configuration file. |
| `GEOSERVER_WORKSPACE`            | `CUT`                          | GeoServer workspace name. |
| `GEOSERVER_ADMIN_USER`           | `admin`                        | Username for GeoServer admin access. |
| `GEOSERVER_ADMIN_PASSWORD`       | `geoserver`                    | Password for GeoServer admin access. |
| `GEOSERVER_BASE_URL`             | `geoserver:8080/geoserver`     | Base URL for GeoServer. |
| `GEOSERVER_PORT`                 | `8080`                         | Port on which GeoServer runs. |
| `GEOSERVER_POSTGIS_HOST`         | `postgis`                      | Hostname of the PostGIS database for GeoServer. |
| `POSTGRES_DB`                    | `cut_dev`                      | Name of the PostgreSQL database. |
| `POSTGRES_USER`                  | `postgres`                     | Username for PostgreSQL. |
| `POSTGRES_PASSWORD`              | `postgres`                     | Password for PostgreSQL. |
| `POSTGRES_HOST`                  | `postgis`                      | Hostname of the PostgreSQL server. |
| `POSTGRES_PORT`                  | `5432`                         | Port of the PostgreSQL server. |
| `PYGEOAPI_CONFIG`                | `/home/pythonuser/pygeoapi-config.yaml` | Path to the PyGeoAPI configuration file. |
| `PYGEOAPI_OPENAPI`               | `/home/pythonuser/pygeoapi-openapi.yaml` | Path to the PyGeoAPI OpenAPI specification. |
| `PYGEOAPI_SERVER_HOST`           | `localhost`                    | Hostname for the PyGeoAPI server. |
| `PYGEOAPI_SERVER_PORT`           | `5000`                         | Port for the PyGeoAPI server. |
| `PYGEOAPI_SERVER_PORT_CONTAINER` | `5005`                         | Internal container port for PyGeoAPI. |
| `DOCKER_NETWORK`                 | `dev`                          | Name of the Docker network. |
| `CONTAINER_REGISTRY`             | `xyz.azurecr.io`               | URL of the container registry. |
| `CONTAINER_NAMESPACE`            | `analytics`                    | Namespace for the container image. |
| `IMAGE_NAME`                     | `urban-model-platform`         | Name of the Docker image. |
| `IMAGE_TAG`                      | `1.1.0`                        | Tag for the Docker image version. |
| `KEYCLOAK_USER`                  | `admin`                        | Admin username for Keycloak. |
| `KEYCLOAK_PASSWORD`              | `admin`                        | Admin password for Keycloak. |
| `KEYCLOAK_HOST`                  | `<<INSERT_YOUR_IP>>`           | Hostname or IP of the Keycloak server. |
| `KEYCLOAK_PROTOCOL`              | `http`                         | Protocol used to access Keycloak (http/https). |
