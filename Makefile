.ONESHELL:
SHELL=/bin/bash

.PHONY: build initiate-dev build-image upload-image start-dev \
        start-dev-example restart-dev stop-dev build-docs clean-docs \
        start-geoserver-db stop-geoserver-db initiate-prod start-prod \
        stop-prod restart-prod clean-prod

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
	docker compose -f docker-compose-build.yaml build \
	--build-arg SOURCE_COMMIT=$(GIT_COMMIT) \
	--build-arg TAG=$(IMAGE_TAG) \
	api

upload-image: build-image
	docker compose -f docker-compose-build.yaml push api

start-dev:
	@ echo 'Starting development environment containers: ump database, geoserver database, geoserver, keycloak, keycloak database'
	docker compose -f docker-compose-dev.yaml up -d api-db geoserver-db keycloak kc-db geoserver
	
	@ echo 'Waiting for databases to be ready'
	sleep 10

	@ echo 'Activating conda environment and running flask commands'
	$(CONDA_ACTIVATE) ./.venv && \
	FLASK_APP=src/ump/main.py flask db upgrade && \
	FLASK_APP=src/ump/main.py flask db current
	
	@ echo 'Starting Flask development server...'
	$(CONDA_ACTIVATE) ./.venv && \
	FLASK_APP=src/ump/main.py FLASK_ENV=development flask run --host=0.0.0.0 --port=5000 --debug


start-dev-example: start-dev
	@echo 'Starting development environment containers: ump database, geoserver, keycloak, keycloak database and an example modelserver'
	docker compose -f docker-compose-dev.yaml up -d modelserver

restart-dev:
	docker compose -f docker-compose-dev.yaml restart

stop-dev:
	docker compose -f docker-compose-dev.yaml stop

clean-dev:
	@echo 'Removing dev containers AND volumes. All data is lost!'
	docker compose -f docker-compose-dev.yaml down --volumes

build-docs:
	jupyter-book build docs

clean-docs:
	jupyter-book clean docs

# Update app version: bump major, minor, or patch
bump-app-version:
	@if [ -z "$(part)" ]; then \
		echo "Usage: make bump-app part={major|minor|patch}"; \
		exit 1; \
	fi; \
	bump-my-version bump $(part)

# Update app version: set to a specific version
set-app-version:
	@if [ -z "$(version)" ]; then \
		echo "Usage: make set-app-version version={version}"; \
		exit 1; \
	fi; \
	bump-my-version set $(version)

# Update chart version: bump major, minor, or patch
bump-chart-version:
	@if [ -z "$(part)" ]; then \
		echo "Usage: make bump-chart part={major|minor|patch}"; \
		exit 1; \
	fi; \
	(cd charts && bump-my-version bump $(part))

# Production environment setup and management
initiate-prod:
	@echo 'Setting up production environment files...'
	
	@if [ ! -f .env.prod ]; then \
		cp .env.prod.example .env.prod; \
		echo 'Created .env.prod from .env.prod.example - Please configure production values!'; \
		echo 'Important: Update database passwords, API URLs, and registry settings'; \
		echo 'See .env.prod.example for production-specific guidance'; \
	else \
		echo '.env.prod already exists'; \
	fi

	@if [ ! -f providers.yaml ]; then \
		cp providers.yaml.example providers.yaml; \
		echo 'Created providers.yaml from providers.yaml.example'; \
	else \
		echo 'providers.yaml already exists'; \
	fi

	@echo 'Creating docker network for production'
	docker network create ump_prod 2>/dev/null || echo 'Network ump_prod already exists'

	@echo ''
	@echo '=== PRODUCTION SETUP COMPLETE ==='
	@echo 'Next steps:'
	@echo '1. Edit .env.prod with your production configuration'
	@echo '2. Update providers.yaml with your model providers'
	@echo '3. Run "make start-prod" to start the production environment'
	@echo '=================================='

start-prod:
	@echo 'Starting production environment...'
	@if [ ! -f .env.prod ]; then \
		echo 'Error: .env.prod not found. Run "make initiate-prod" first.'; \
		exit 1; \
	fi
	
	@echo 'Building and starting production containers'
	docker compose -f docker-compose-prod.yaml --env-file .env.prod up -d --build
	
	@echo 'Waiting for databases to be ready...'
	sleep 15
	
	@echo 'Running database migrations...'
	docker compose -f docker-compose-prod.yaml --env-file .env.prod exec api flask db upgrade
	
	@echo ''
	@echo '=== PRODUCTION ENVIRONMENT STARTED ==='
	@echo 'Check status with: docker compose -f docker-compose-prod.yaml --env-file .env.prod ps'
	@echo 'View logs with: docker compose -f docker-compose-prod.yaml --env-file .env.prod logs -f'
	@echo '======================================='

stop-prod:
	@echo 'Stopping production environment...'
	docker compose -f docker-compose-prod.yaml --env-file .env.prod stop

restart-prod:
	@echo 'Restarting production environment...'
	docker compose -f docker-compose-prod.yaml --env-file .env.prod restart

clean-prod:
	@echo 'WARNING: This will remove all production containers AND volumes!'
	@echo 'All production data will be lost!'
	@read -p "Are you sure? Type 'yes' to continue: " confirm && [ "$$confirm" = "yes" ] || exit 1
	docker compose -f docker-compose-prod.yaml --env-file .env.prod down --volumes
	@echo 'Production environment cleaned'

# Production utilities
prod-logs:
	@echo 'Showing production logs (Ctrl+C to exit)...'
	docker compose -f docker-compose-prod.yaml --env-file .env.prod logs -f

prod-status:
	@echo 'Production environment status:'
	docker compose -f docker-compose-prod.yaml --env-file .env.prod ps

prod-shell:
	@echo 'Opening shell in production API container...'
	docker compose -f docker-compose-prod.yaml --env-file .env.prod exec api /bin/bash