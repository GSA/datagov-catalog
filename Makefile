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

poetry-update: ## Updates local Poetry to latest
	poetry self update


update-dependencies: ## Updates requirements.txt and requirements_dev.txt from pyproject.toml
	poetry export --without-hashes --without=dev --format=requirements.txt > requirements.txt
	poetry export --without-hashes --only=dev --format=requirements.txt > requirements-dev.txt

test-ci: up test

test:
	poetry run pytest

test-pa11y: ## Runs accessibility tests with pa11y-ci (requires running app)
	npm run test:pa11y

load-test-data: ## Loads test fixture data into the database
	docker compose exec app flask testdata load_test_data --clear
	docker compose exec app flask search sync

test-a11y-with-data: up load-test-data test-pa11y ## Runs accessibility tests with test data loaded

up: ## Sets up local flask  docker environment.
	docker compose up -d --wait

up-debug: ## Sets up local docker environment with VSCODE debug support enabled
	docker compose -f docker-compose.yml -f docker-compose_debug.yml up -d --wait

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
