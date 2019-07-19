#!/usr/bin/env bash

docker-compose build

PROJECT_NAME=heos-scrobbler

# Hack to determine whetever or not to initiate Mongo replica set
set -o pipefail
docker volume ls | grep -q ${PROJECT_NAME}_mongo[^-express]
MONGO_INITIATE_REPLICA_SET=$?
set +o pipefail

set -o allexport
source mongo/.env
set +o allexport

docker-compose -p ${PROJECT_NAME} up -d --no-recreate mongo mongo-express

if [ "${MONGO_INITIATE_REPLICA_SET}" != "0" ]; then
  MONGO_HOST=localhost

  until nc -z ${MONGO_HOST} ${MONGO_PORT}
  do
      echo "Waiting for Mongo ${MONGO_HOST}:${MONGO_PORT} to start..."
      sleep 1
  done

  echo "Initializing Mongo replica set and database"

  until docker-compose -p ${PROJECT_NAME} exec mongo mongo -u ${MONGO_INITDB_ROOT_USERNAME} -p ${MONGO_INITDB_ROOT_PASSWORD} admin --eval "rs.initiate()"
  do
    echo "Waiting for Mongo to accept connections..."
    sleep 1
  done

  SET_MONGO_SHELL_ENVIRONMENT_COMMAND="var heosScrobblerUser = '${MONGO_HEOS_SCROBBLER_USER}'; var heosScrobblerPassword = '${MONGO_HEOS_SCROBBLER_PASSWORD}';"

  docker-compose -p ${PROJECT_NAME} exec mongo mongo -u ${MONGO_INITDB_ROOT_USERNAME} -p ${MONGO_INITDB_ROOT_PASSWORD} admin --eval "${SET_MONGO_SHELL_ENVIRONMENT_COMMAND}" /usr/src/initialize.js
fi

docker-compose -p ${PROJECT_NAME} up -d --no-deps --force-recreate heos-track-listener heos-track-scrobbler

docker-compose -p ${PROJECT_NAME} logs --follow heos-track-listener heos-track-scrobbler
