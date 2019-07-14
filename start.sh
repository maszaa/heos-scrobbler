#!/usr/bin/env bash

docker-compose build

export WORKERS=$(nproc)
docker-compose up -d heos-track-listener heos-track-scrobbler

docker-compose logs --follow
