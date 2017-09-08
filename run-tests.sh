#!/usr/bin/env bash

set -euf -o pipefail

# Setup
ansible-galaxy install -r "${DATA_DIRECTORY}/tests/integration/requirements.yml"
pip install -r "${DATA_DIRECTORY}/tests/integration/requirements.txt"

# Run unit tests
PYTHONPATH=. python -m unittest discover -v -s tests/unit

# Run integration tests
ansible-playbook -vvv -e ansible_python_interpreter=$(which python) -c local "${DATA_DIRECTORY}/tests/integration/site.yml"
