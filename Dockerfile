FROM python:3.12-alpine3.22

# Pull the latest patched packages from the base distro.
RUN apk upgrade --no-cache

WORKDIR /app

COPY . /app

RUN pip install poetry

# poetry try use virtualenv if .venv is present
RUN poetry config virtualenvs.create false
RUN rm -rf /app/.venv 

RUN poetry install --without=dev --no-root

# datagov-data-access is a dev-only dependency of the app itself (catalog is
# read-only in production) but the local/CI container still needs it to run
# `flask search compare` and `flask testdata load_test_data` against a local
# OpenSearch, via `make load-test-data`. It's kept in its own group,
# separate from `dev`, because `dev` also carries playwright, which has no
# musl/Alpine wheels and can't install in this image.
RUN poetry install --without=dev --with=container-dev --no-root

ARG DEV

RUN if [ $DEV ]; \
    then poetry install --with=dev; \
    fi

EXPOSE 8080

ENV FLASK_APP=run.py

# Run run.py when the container launches
CMD ["/bin/sh", "-c", "flask run --host=0.0.0.0 --port=8080"]
