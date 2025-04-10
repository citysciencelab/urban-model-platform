# Contributing

Contributions are welcome, and they are greatly appreciated!
Every little bit helps, and credit will always be given.

If you have a suggestion for improvements, please fork the repo and create a pull request. You can also simply open an issue. Don't forget to star and rate the project! Thanks again!

1. Fork the Project
1. Create your Feature Branch (git checkout -b feature/AmazingFeature)
1. Commit your Changes (git commit -m 'Add some AmazingFeature')
1. Push to the Branch (git push origin feature/AmazingFeature)
1. Open a Pull Request


Here is how to set up the project locally for development:


## Initial setup
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

A conda `environment.yaml` is provided inside this repo.

In order to create an external docker network to connect your containers to, run:
`docker network create dev`




## Installing dependencies

Install the projects code and all dependencies with:

```bash
poetry install
```

you can add packages with:
```bash
poetry add PACKAGE-NAME
```

You can remove packages by using:
```bash
poetry remove PACKAGE-NAME
```

Packages can be updated with: 
```bash
poetry update PACKAGE-NAME
```

In order to run an example modelserver, git submodule is used and needs to be initiated:

```bash
git submodule init
```
```bash
git submodule update --recursive
```

In this folder you can find build instructions to build a container with OGC API Processes compliant example processes based on pygeoapi. Those can be utilized as example processes for the Urban Model Platform. For it to run, `cd moduleserver_example`and run:
- `cp .env.example .env` and set `IMAGE_TAG` to `main`
-  `docker compose -f docker-compose-build.yaml build`


## Updating the Documentation
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
To start the Flask app, run:
```python
flask -A src/ump/main.py --debug run
```

## Data Storage

The Urban Model Platform uses Docker containers to run the PostGIS and Geoserver components. The data is stored in the following folders:

* `postgresql_data` -> contains the postgres db files
* `geoserver_data` -> contains the Geoserver data dir


If you are in development and want to reset all PostGis and Geoserver data, you can delete the `postgresql_data` and the `geoserver_data` folders.

## DB-Migrations
The Urban Model Platform uses Alembic for database migrations. The migration scripts are located in the `src/ump/migrations` folder. To run the migrations, use the following command:

```bash
alembic upgrade head
```
This will apply all pending migrations to the database.