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
	
