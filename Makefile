.ONESHELL:
SHELL=/bin/bash

.PHONY: build initiate-dev build-image upload-image start-dev \
        start-dev-example restart-dev stop-dev build-docs clean-docs

config ?= .env

# Überprüfen und erstellen der .env-Datei, falls sie nicht existiert
$(shell [ -f $(config) ] || cp .env.example $(config))

include $(config)
export $(shell sed 's/=.*//' $(config))

# Note that the extra activate is needed to ensure that the activate floats env to the front of PATH
CONDA_ACTIVATE=source $$(conda info --base)/etc/profile.d/conda.sh ; conda activate; conda activate

GIT_COMMIT := $(shell git rev-parse --short HEAD)


initiate-dev:
	@if [ ! -d ./.venv ]; then \
		echo 'Creating conda environment in ./.venv'; \
		conda env create -f environment.yaml -p ./.venv; \
	else \
		echo 'Conda environment (./.venv) already present'; \
    fi

	@if [ ! -f providers.yaml ]; then \
		cp providers.yaml.example providers.yaml \
		echo 'Creating providers.yaml from providers.yaml.example'; \
	else \
		echo 'providers.yaml already present'; \
	fi

	@if [ ! -f .env ]; then \
		cp .env.example .env \
		echo 'Creating .env from .env.example'; \
	else \
		echo '.env already present'; \
	fi

	@ echo 'Creating docker network for development'
	docker network create ump_dev

	@echo 'Installing app dependencies:'
	poetry install

build-image:
	@echo 'Building release ${CONTAINER_REGISTRY}/${CONTAINER_NAMESPACE}/$(IMAGE_NAME):$(IMAGE_TAG)'
# build your image
	docker compose -f docker-compose-build.yaml build --build-arg SOURCE_COMMIT=$(GIT_COMMIT) api

upload-image: build-image
	docker compose -f docker-compose-build.yaml push api

start-dev:
	($(CONDA_ACTIVATE) ./.venv)

	@ echo 'Starting development environment containers: ump database, geoserver, keycloak, keycloak database'
	
	docker compose -f docker-compose-dev.yaml up -d api-db geoserver keycloak kc-db

	@ initilize the database
	flask db init

	@ echo running database migrations
	flask db upgrade

	@ echo 'Current database state'
	flask db current
	
	@ echo 'Now start a debug session with your preferred IDE, e.g. VSCode using launch.json'


start-dev-example: start-dev
	@echo 'Starting development environment containers: ump database, geoserver, keycloak, keycloak database and an example modelserver'
	docker compose -f docker-compose-dev.yaml up -d modelserver

restart-dev:
	docker compose -f docker-compose-dev.yaml restart

stop-dev:
	docker compose -f docker-compose-dev.yaml stop

clean-dev:
	@echo 'Removing dev containers AND volumes'
	docker compose -f docker-compose-dev.yaml down --volumes

build-docs:
	jupyter-book build docs

clean-docs:
	jupyter-book clean docs
