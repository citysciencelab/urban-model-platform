ARG $MAMBA_USER=mambauser

FROM python:3.11-bookworm AS base

ENV CACHE_DIR=/app/cache

WORKDIR /app

RUN --mount=type=cache,target=$CACHE_DIR apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/* \
    && pip install poetry

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/app/poetry_cache

COPY pyproject.toml poetry.lock ./
RUN --mount=type=cache,target=$POETRY_CACHE_DIR poetry install --without=dev --no-root

# maybe needed for psycopg2
# RUN apt update \
#     && apt upgrade -y \
#     && apt install -qq -y --no-install-recommends \
#     libpq-dev gdal-bin libgdal-dev \
#     && apt clean

COPY src ./src
RUN touch README.md \
    && poetry build \
    && /app/.venv/bin/python -m pip install dist/*.whl --no-deps

FROM python:3.11-slim-bookworm AS runtime

ARG USER_UID=1000
ARG USERNAME=pythonuser
ARG USER_GID=2000
ARG SOURCE_COMMIT

LABEL maintainer="Urban Data Analytics" name="analytics/mobilitatsmonitor_dashboard" source_commit=$SOURCE_COMMIT

# add user and group
RUN groupadd --gid $USER_GID $USERNAME && \
    useradd --create-home --no-log-init --gid $USER_GID --uid $USER_UID --shell /bin/bash $USERNAME && \
    chown -R $USERNAME:$USERNAME /home/$USERNAME /usr/local/lib /usr/local/bin

USER $USERNAME
WORKDIR /home/$USERNAME

ENV VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

COPY --from=base \
    --chmod=0755 \
    --chown=$USERNAME:$USERNAME \
    /app/.venv /app/.venv

COPY scripts/entrypoint.sh entrypoint.sh

EXPOSE 5000

ENTRYPOINT [ "/home/pythonuser/entrypoint.sh" ]
