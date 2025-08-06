# Setup

This document describes the configuration options for the Urban Model Platform (UMP). The configuration is managed using environment variables, which can be set in the `.env` file. Below is a detailed explanation of the available configuration options.

## Environment Variables

### App Settings
| Variable                              | Description                                                                                     | Default Value          |
|---------------------------------------|-------------------------------------------------------------------------------------------------|------------------------|
| `UMP_LOG_LEVEL`                       | Logging level for the application.                                                             | `DEBUG`               |
| `UMP_PROVIDERS_FILE`                  | Path to the providers configuration file.                                                      | `providers.yaml`      |
| `UMP_API_SERVER_URL`                  | Base URL of the API server. Used in job details responses.                                      | `localhost:5000`      |
| `UMP_REMOTE_JOB_STATUS_REQUEST_INTERVAL` | Interval (in seconds) for checking remote job statuses.                                         | `5`                   |
| `UMP_DATABASE_NAME`                   | Name of the PostgreSQL database.                                                               | `ump`                 |
| `UMP_DATABASE_HOST`                   | Hostname of the PostgreSQL database.                                                           | `localhost`           |
| `UMP_DATABASE_PORT`                   | Port of the PostgreSQL database.                                                               | `5433`                |
| `UMP_DATABASE_USER`                   | Username for the PostgreSQL database.                                                          | `ump`                 |
| `UMP_DATABASE_PASSWORD`               | Password for the PostgreSQL database.                                                          | `ump`                 |
| `UMP_GEOSERVER_URL`                   | URL of the GeoServer instance.                                                                 | `http://geoserver:8080/geoserver` |
| `UMP_GEOSERVER_DB_HOST`               | Hostname of the GeoServer database.                                                            | `localhost`           |
| `UMP_GEOSERVER_DB_PORT`               | Port of the GeoServer database.                                                                | `5432`                |
| `UMP_GEOSERVER_WORKSPACE_NAME`        | Name of the GeoServer workspace.                                                               | `UMP`                 |
| `UMP_GEOSERVER_USER`                  | Username for GeoServer.                                                                        | `admin`               |
| `UMP_GEOSERVER_PASSWORD`              | Password for GeoServer.                                                                        | `geoserver`           |
| `UMP_GEOSERVER_CONNECTION_TIMEOUT`    | Timeout (in seconds) for GeoServer connections.                                                | `60`                  |
| `UMP_JOB_DELETE_INTERVAL`             | Interval (in minutes) for cleaning up old jobs.                                                | `240`                 |
| `UMP_KEYCLOAK_URL`                    | URL of the Keycloak server.                                                                    | `http://keycloak:8080`|
| `UMP_KEYCLOAK_REALM`                  | Keycloak realm name.                                                                           | `UrbanModelPlatform`  |
| `UMP_KEYCLOAK_CLIENT_ID`              | Keycloak client ID.                                                                            | `ump-client`          |
| `UMP_KEYCLOAK_USER`                   | Keycloak admin username.                                                                       | `admin`               |
| `UMP_KEYCLOAK_PASSWORD`               | Keycloak admin password.                                                                       | `admin`               |
| `UMP_API_SERVER_URL_PREFIX`           | subpath prefix, e.g.: "/api"                                                                   | `/`                   |

### Example Modelserver Settings
| Variable                              | Description                                                                                     | Default Value          |
|---------------------------------------|-------------------------------------------------------------------------------------------------|------------------------|
| `PYGEOAPI_SERVER_HOST`                | Hostname for the example modelserver.                                                          | `localhost`           |
| `PYGEOAPI_SERVER_PORT_INTERNAL`       | Internal port for the example modelserver.                                                     | `5000`                |
| `PYGEOAPI_SERVER_PORT_EXTERNAL`       | External port for the example modelserver.                                                     | `5005`                |

### Docker Dev Environment Settings
| Variable                              | Description                                                                                     | Default Value          |
|---------------------------------------|-------------------------------------------------------------------------------------------------|------------------------|
| `DOCKER_NETWORK`                      | Name of the Docker network for the development environment.                                     | `ump_dev`             |
| `WEBAPP_PORT_EXTERNAL`                | External port for the UMP web application.                                                     | `5003`                |
| `API_DB_PORT_EXTERNAL`                | External port for the PostgreSQL database used by the API.                                      | `5433`                |
| `GEOSERVER_PORT_EXTERNAL`             | External port for the GeoServer instance.                                                      | `8181`                |
| `KEYCLOAK_PORT_EXTERNAL`              | External port for the Keycloak instance.                                                       | `8282`                |

### Docker Build Settings
| Variable                              | Description                                                                                     | Default Value          |
|---------------------------------------|-------------------------------------------------------------------------------------------------|------------------------|
| `CONTAINER_REGISTRY`                  | Container registry URL.                                                                         | `registry.io`         |
| `CONTAINER_NAMESPACE`                 | Namespace for the container registry.                                                          | `namespace`           |
| `IMAGE_NAME`                          | Name of the Docker image.                                                                      | `urban-model-platform`|
| `IMAGE_TAG`                           | Tag for the Docker image.                                                                      | `1.1.0`               |

---

## Testing and running the Application
Docker containers are used to ease the setup of required services: PostgreSQL database(s), GeoServer and Keycloak.

There are two ways to test the application:

### 1. Using Docker Compose
You can build and run the application in a containerized environment using the provided Docker Compose files:
   ```bash
   make initiate-dev
   ```

   Then, adjust the newly created .env file to your needs. After that run:
   
   ```bash
   make build-image
   make start-dev # or make start-dev-example
   docker compose -f docker-compose-dev.yaml up api -d
   ```

### 2. Running the app locally
Alternatively, you can run the application locally:
   ```bash
   make initiate-dev
   make start-dev # or make start-dev-example
   gunicorn --workers=1 --bind=0.0.0.0:5000 ump.main:app
   ```

Both methods will set up the necessary dependencies (PostgreSQL, GeoServer, Keycloak) for the application to function correctly.


**Either use the provided Makefile:**
```bash
make initiate-dev
```
Then, adjust the newly created .env file to your needs.

**Or do it manually:**

1. Create a virtual python environment:
   ```bash
   conda env create -f environment.yaml
   ```

1. Copy providers.yaml:
    ```bash
    cp providers.yaml.example providers.yaml
    ```

1. Copy .env.example
   ```bash
   cp .env.example .env
   ```

1. Start the required apps with
   ```bash
   make start-dev
   ```

1. Or start them with an example process
   ```bash
   make start-dev-example
   ```
---

Enjoy!