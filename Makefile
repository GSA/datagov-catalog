SHELL=/bin/bash -o pipefail

all: help

build:  ## build Flask app
	docker compose build app

build-dev:  ## build Flask app w/ dev dependencies
	docker compose build app --build-arg DEV=True

install-static: ## Installs static assets
	cd app/static; \
	npm install; \
	npm run build


update-dependencies: ## Updates requirements.txt and requirements_dev.txt from pyproject.toml
	poetry export --without-hashes --without=dev --format=requirements.txt > requirements.txt
	poetry export --without-hashes --only=dev --format=requirements.txt > requirements-dev.txt

# OpenSearch takes a while to start up so sleep
test-ci: up sleep test

sleep:
	sleep 20

test:
	poetry run pytest

up: ## Sets up local flask  docker environment.
	docker compose up -d

up-debug: ## Sets up local docker environment with VSCODE debug support enabled
	docker compose -f docker-compose.yml -f docker-compose_debug.yml up -d

down: ## Tears down the flask and harvester containers
	docker compose down

clean: ## Cleans docker images
	docker compose down -v --remove-orphans

lint:  ## Lints wtih ruff, isort, black
	poetry run ruff check .
	poetry run isort .
	poetry run black .

# Output documentation for top-level targets
# Thanks to https://marmelab.com/blog/2016/02/29/auto-documented-makefile.html
.PHONY: help

help: ## This help
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "\033[36m%-10s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
