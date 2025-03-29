
## Dev environment setup

### Initial setup
You only need two tools, [Poetry](https://github.com/python-poetry/poetry)
and [Copier](https://github.com/copier-org/copier).

Poetry is used as a package manager. Copier is used for the project structure (scaffolding).


Install with pip:
```bash
python3 -m pip install --user pipx
pipx install poetry
pipx install copier copier-templates-extensions
```

Or create a new environment with conda/mamba:

```bash
conda env create -f environment.yaml -p ./.venv
```

If you have a conda environment and want to use the Makefile, use following command: 
```bash
make initiate-dev
``` 

A conda [environment.yaml](./environment.yaml) is provided inside this repo.

In order to create an external docker network to connect your containers to, run:
`docker network create dev`


### Dev setup

Install the projects code and all dependencies with:

```bash
poetry install
```
In order to run an example modelserver, git submodule is used and needs to be initiated:
`git submodule init`
`git submodule update --recursive`

In this folder you can find build instructions to build a container with OGC API Processes compliant example processes based on pygeoapi. Those can be utilized as example processes for the Urban Model Platform. 


## Running tests

## Serving docs


Install the optional docs depdendencies with:

```bash
poetry install --only=docs
```

Run the build process with:

```bash
make build-docs
```

To view the docs copy the content of the [docs/_build](./docs/_build) folder to a webserver or use VSCode and the [Live server extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode.live-server).

## Start Flask App
flask -A src/ump/main.py --debug run

## Package Management
Poetry is used as a package manager, you can add packages with:
`poetry add PACKAGE-NAME`

You can remove packages by using:
`poetry remove PACKAGE-NAME`

Packages can be updated with: 
`poetry update PACKAGE-NAME`




## Prerequisites
- Docker

## Setup Development
The components are configured in a docker-compose setup with nginx as a proxy.

To initialize the dev environment:

* run `git submodule update --init --recursive` (only needed once)
* `cp .env.example .env`
* in `moduleserver_example`: (only needed once)
  * `cp .env.example .env` and set `IMAGE_TAG` to `main`
  * run `docker compose -f docker-compose-build.yaml build`
* on top level, run `docker compose -f docker-compose-local.yaml up --build`

After that you can access the app like follows:

* http://localhost/api/ -> used to access the api itself
* http://localhost/geoserver/ -> used to access the Geoserver frontend and services

Persistent data is stored as follows:

* `postgresql_data` -> contains the postgres db files
* `geoserver_data` -> contains the Geoserver data dir

## Alternate dev setup
If you prefer a more native approach running flask locally on your computer, see `CONTRIBUTING.md` for an alternate approach.

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

## DB-Migrations
Currently the DB uses Flask-Migrate and must be migrated manually using `flask db upgrade` when new migrations are available.

## Keycloak
In order to configure a dev setup Keycloak initially, log in with admin/admin. Then:

* create a new realm named `UrbanModelPlatform`
* create a new client in that realm called `ump-client`
* create a test user called `ump`, set its password to `ump`
* make sure to set the keycloak host in `.env` to your local hostname or IP address

## Try it out

```bash
curl localhost/api/processes/modelserver:squareroot/execution -H "Content-Type: application/json" -d '{"inputs": {"number": 4}}'
```

After that look up the result urls using the jobs api:

```bash
curl localhost/api/jobs/
```

See the swagger docs at http://localhost/docs
