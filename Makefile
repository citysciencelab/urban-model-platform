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
	cp providers.yaml.example providers.yaml
	cp .env.example .env

build-image:
	@echo 'Building release ${CONTAINER_REGISTRY}/analytics/$(IMAGE_NAME):$(IMAGE_TAG)'
# build your image
	docker compose -f docker-compose-build.yaml build --build-arg SOURCE_COMMIT=$(GIT_COMMIT) app

upload-image: build-image
	docker compose -f docker-compose-build.yaml push app

start: stop
	docker compose -f docker-compose.yaml up -d nginx
	docker compose -f docker-compose.yaml up geoserver api

start_prod: stop
	docker compose -f docker-compose.prod.yaml up geoserver api postgis

restart: stop start

stop:
	docker-compose down

install:
	docker compose build api
	docker compose run --rm api pip install --user --upgrade --no-cache-dir -r requirements.txt

install_prod:
	sudo docker compose -f docker-compose.prod.yaml build api
	sudo docker compose -f docker-compose.prod.yaml run --rm api pip install --user --upgrade --no-cache-dir -r requirements.txt
	
