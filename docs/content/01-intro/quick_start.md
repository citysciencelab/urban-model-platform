(quickstart)=
# Quick Start

This section provides a quick start guide to get you up and running with the Urban Model Platform. It covers the basic steps to set up your development environment, run the application, and test it.

## Requirements
- Docker
- Docker Compose
- Python 3.8 or higher
- Conda (only for local development)
- Poetry (only for local development)

## Installation
To install the Urban Model Platform, follow these steps:

1. Clone this repository by using ```git clone git@github.com:citysciencelab/urban-model-platform.git```
2. Navigate to the project directory: ```cd urban-model-platform```   
4. Initiate the development environment by running: ```make initiate-dev```
5. Build the Docker containers by running: ```make build-image```
6. Start the local development environment by running: ```make start-dev```

```{note}
This will start the Urban Model Platform and all its dependencies, including Keycloak, PostgreSQL, and GeoServer.
```

```{note}
If you want to also start an example model server, make sure to initialize the git submodule and run the following command:
```git submodule update --init --recursive```

Then, you can start the model server by running:
```make start-dev-with-modelserver```

```

## Accessing the Application
Once the application is running, you can access it at the following URLs:
- Urban Model Platform: [http://localhost:5003](http://localhost:5003)
- Keycloak: [http://localhost:8282](http://localhost:8282)
- GeoServer: [http://localhost:8080](http://localhost:8080)
- PostgreSQL: [http://localhost:5432](http://localhost:5432)
- Example Model Server (only if set up): [http://localhost:5005](http://localhost:5005)


## Configuring Providers
Providers of processes and model servers are defined in the [`providers.yaml`](../../providers.yaml) file. This file contains the configuration for connecting to external model servers and processes. Each provider entry specifies the necessary details, such as the server URL, authentication credentials, and process identifiers. Find more information about the providers in the [providers documentation](providers).

```{note}
The `providers.yaml` file is essential for the Urban Model Platform to interact with external model servers and processes. Make sure to configure it correctly to ensure seamless integration.
```


## Configuring Keycloak
Keycloak is used for authentication and authorization in the Urban Model Platform. To configure Keycloak, follow these steps:
1. Open Keycloak on [http://localhost:8282/auth](http://localhost:8282/auth)
2. Log in with the admin credentials (admin/admin).
3. Create a new realm named `UrbanModelPlatform`.
4. Create a new client in that realm called `ump-client` (activate OAuth 2.0 Device Authorization Grant and Direct access grants).
5. Create a test user called `ump`, set its password to `ump`.

```{note}
If a process is not configured with  ```anonymous-access: True``` in [`providers.yaml`](../../providers.yaml), one has to give users the permission access the process. This can be done in two ways:

1. By adding the user to a specific client role `modelserverID_processID` in Keycloak. This will give the user access only to the specific process.
2. By adding the user to a specific client role `modelserverID` in Keycloak. This will give the user access to all processes of the model server with the specified id. 

 `modelserverID` and `processID` correspond to the keys used in the [`providers.yaml`](../../providers.yaml) file.

```