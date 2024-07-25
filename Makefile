.ONESHELL:
SHELL=/bin/bash
.PHONY: build

config ?= .env

include $(config)
export $(shell sed 's/=.*//' $(config))

# Note that the extra activate is needed to ensure that the activate floats env to the front of PATH
CONDA_ACTIVATE=source $$(conda info --base)/etc/profile.d/conda.sh ; conda activate; conda activate

GIT_COMMIT := $(shell git rev-parse --short HEAD)


initiate-dev:
	conda env create -f environment.yaml -p ./.venv
	cp providers.yaml.example providers.yaml -n
	cp .env.example .env -n

build-image:
	@echo 'Building release ${CONTAINER_REGISTRY}/analytics/$(IMAGE_NAME):$(IMAGE_TAG)'
# build your image
	docker compose -f docker-compose-build.yaml build --build-arg SOURCE_COMMIT=$(GIT_COMMIT) app

upload-image: build-image
	docker compose -f docker-compose-build.yaml push app

start-dev: stop-dev
	docker compose -f docker-compose-dev.yaml up geoserver postgis modelserver
	flask -A src/ump/main.py --debug run

restart-dev: stop-dev start-dev

stop-dev:
	docker compose -f docker-compose-dev.yaml down

build-docs:
	jupyter-book build docs

clean-docs:
	jupyter-book clean docs