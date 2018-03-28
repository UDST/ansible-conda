#!/usr/bin/env bash
set -euf -o pipefail

docker-compose -f tests/unit/docker/docker-compose.test.yml up \
    --build --force-recreate --remove-orphans

docker-compose -f tests/integration/docker/docker-compose.test.yml up \
    --build --abort-on-container-exit --exit-code-from ansible-conda-integration-test-runner --force-recreate --remove-orphans
