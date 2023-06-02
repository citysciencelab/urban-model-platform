<img src="https://github.com/citysciencelab/urban-model-platform/assets/61881523/262b510c-acd6-4374-9bfd-5e39160d0c54" height="150">

<img src="https://github.com/citysciencelab/urban-model-platform/assets/61881523/ef1540b9-1489-44cd-84fc-dfdb32820a1f" height="170" padding="0 0 0 50">

# Urban Model Platform
The repository contains a Python implementation of the OGC API Processes standard that can be used as a "system of systems" open platform. In the context of digital urban twins, such a platform can provide the infrastructure to integrate and combine domain-specific models ranging from simple regression models to advanced simulation or AI models. 
Instead of executing jobs and processes on the server itself, the Urban Model Platform is configured with multiple **providers** or model servers (see configuration below). 
This architecture is independent of any frontend application. One could use e.g. - as shown in the illustration below - the Masterportal Simulation Controller as a client frontend, but due to the standardized API, mutliple frontends are possible. 

![Architektur](https://user-images.githubusercontent.com/61881523/232417254-a620fd2c-bd1c-416a-ae64-b0f564fd64cc.jpg)

## Prerequisites
- Docker

## Setup Development
The components are configured in a docker-compose setup with nginx as a proxy.

After you added the below configurations you can install and start the application with

```
make install
make start
```

There are also
```
make restart
make stop
```
commands available (see Makefile).

## Geoserver configuration
The Geoserver uses two configuration files:
- geoserver/configs/geoserver
- geoserver/configs/postgis

Please copy and adapt the example files from geoserver/configs/geoserver.example and postgis.example. The example files include example values for a development setup.

Currently all results are stored to the Geoserver in a single workspace (e.g. "CUT"). The stores and layers are named by their job ids with the prefix "job-".

The workspace name is configured by the backend api but also has to be configured by the frontend.

The geoserver stores its data into the folder geoserver/data/geoserver. This is configured in the docker-compose.yaml file.

## PostGIS configuration
PostGIS is configured in geoserver/configs/postgis. The api also loads these env variables by loading geoserver/configs/postgis in the docker-compose files.

The data is stored in geoserver/data/pg_data as configured in docker-compose.yaml (development) and docker-compose.prod.yaml (production). If you want to run development and production on the same server, the data should be written to separate paths.

## nginx configuration
The nginx configuration can be found at nginx/default.conf. It configures the paths to the respective endpoints.
There are no changes necessary for development.

## Backend api configuration
- api/configs/dev_environment
- api/configs/providers.yml

Both configuration files have example files in the api/configs folder.

The **dev_environment** file is loaded by docker-compose. In a production environment you can create a prod_environment file with your settings and use it instead of the dev_environment setting in docker-compose. The dev_environment.example file can be copied over as is for development.

The **providers** file sets up the remote simulation model servers. The implemented backend loads **all** models (= processes) from the configured simulation model servers except the ones explicitely excluded.

The simulation model servers have to provide endpoints that comply with the OGC processes api standard in order to be loaded from this api (see https://ogcapi.ogc.org/processes/). Otherwise they will be silently ignored. An error will be logged.

In case the **providers** file needs to be modified, the server has to be restarted (make restart).


### Production Container

A production ready container for the frontend is configured under `frontend_prod` in the docker-compose file. Run `docker-compose build frontend_prod` to create this container which includes a production build of the frontend portal files. The command `docker-compose up frontend_prod` will serve the portal on the defined port.

## Routes
If not configured differently in nginx/default.conf, then:

The **frontend** is available under localhost:3000. Click on the link "portal" -> "simulation" and then choose "Werkzeuge" -> "Simulation Tool".

The **Geoserver** is available under localhost:3000/geoserver. Choose "Layer previews" in the menu to see the list of uploaded layers. If you click on OpenLayers then the data will be displayed in a new tab.

The **backend api** is available under localhost:3000/api.

## Deployment
After configurations are done for production, for deployment you can run
```
make install_prod
make start_prod
```
It will use the provided docker-compose.prod.yaml file together with the nginx default.conf settings.

## Reset data in development
If you are in development and want to reset all PostGis and Geoserver data, you can safely delete the geoserver/data folder completely.
