FROM python:3.12-alpine3.22

# Pull patched packages and require the Alpine 3.22 zlib security fix.
RUN apk upgrade --no-cache \
    && apk add --no-cache 'zlib>=1.3.2-r1'

WORKDIR /app

COPY . /app

RUN pip install poetry

# poetry try use virtualenv if .venv is present
RUN poetry config virtualenvs.create false
RUN rm -rf /app/.venv 

RUN poetry install --without=dev --no-root

ARG DEV

RUN if [ $DEV ]; \
    then poetry install --with=dev; \
    fi

EXPOSE 8080

ENV FLASK_APP=run.py

# Run run.py when the container launches
CMD ["/bin/sh", "-c", "flask run --host=0.0.0.0 --port=8080"]
