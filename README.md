![ump_csl](https://github.com/citysciencelab/urban-model-platform/assets/61881523/1038090d-6c33-4d90-80cc-b1481d51a5a7)


# Urban Model Platform
The repository contains a Python implementation of the OGC API Processes standard that can be used as a "system of systems" open platform. In the context of digital urban twins, such a platform can provide the infrastructure to integrate and combine domain-specific models ranging from simple regression models to advanced simulation or AI models.
Instead of executing jobs and processes on the server itself, the Urban Model Platform is configured with multiple **providers** or model servers (see configuration below).
This architecture is independent of any frontend application. One could use e.g. - as shown in the illustration below - the Masterportal Simulation Controller as a client frontend, but due to the standardized API, mutliple frontends are possible.

![Architektur](https://user-images.githubusercontent.com/61881523/232417254-a620fd2c-bd1c-416a-ae64-b0f564fd64cc.jpg)

## Prerequisites
- Docker

## Setup Development
The components are configured in a docker-compose setup with nginx as a proxy.

To initialize the dev environment:

* run `git submodule --init --recursive` (only needed once)
* use the top level `.env.example` to see how the top level `.env` should look like
* in `moduleserver_example`: (only needed once)
  * copy the `.env.example` to `.env` and set `IMAGE_TAG` to `main`
  * run `docker compose build`
* on top level, run `docker compose up --build`

After that you can access the app like follows:

* http://localhost/api/ -> used to access the api itself
* http://localhost/geoserver/ -> used to access the Geoserver frontend and services

Persistent data is stored as follows:

* `postgresql_data` -> contains the postgres db files
* `geoserver_data` -> contains the Geoserver data dir

## Geoserver configuration

Currently all results are stored to the Geoserver in a single workspace (e.g. "CUT"). The stores and layers are named by their job ids with the prefix "job-".

The workspace name is configured by the backend api but also has to be configured by the frontend.

## nginx configuration
The nginx configuration can be found at nginx/default.conf. It configures the paths to the respective endpoints.
There are no changes necessary for development.

## Backend api configuration
For the API you'll need a `providers.yaml` on top level. The current state works with the example modelserver from the submodule, the example shows how authentication can be configured.

The **providers** file sets up the remote simulation model servers. The implemented backend loads **all** models (= processes) from the configured simulation model servers except the ones explicitely excluded.

The simulation model servers have to provide endpoints that comply with the OGC processes api standard in order to be loaded from this api (see https://ogcapi.ogc.org/processes/). Otherwise they will be silently ignored. An error will be logged.

In case the **providers** file needs to be modified, the server has to be restarted (make restart).


### Production Container

A production ready container for the frontend is configured under `frontend_prod` in the docker-compose file. Run `docker-compose build frontend_prod` to create this container which includes a production build of the frontend portal files. The command `docker-compose up frontend_prod` will serve the portal on the defined port.

## Deployment
After configurations are done for production, for deployment you can run
```
make install_prod
make start_prod
```
It will use the provided docker-compose.prod.yaml file together with the nginx default.conf settings.

## Reset data in development
If you are in development and want to reset all PostGis and Geoserver data, you can delete the `postgresql_data` and the `geoserver_data` folders.

## Try it out

```bash
curl localhost/api/processes/modelserver:squareroot/execution -H "Content-Type: application/json" -d '{"inputs": {"number": 4}}'
```

After that look up the result urls using the jobs api:

```bash
curl localhost/api/jobs/
```
