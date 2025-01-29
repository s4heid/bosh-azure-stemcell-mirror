#!/bin/bash

set -e

cd "$(cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/.." &> /dev/null && pwd)"

if ! command -v black ; then
    pip install -r requirements-dev.txt
fi

black --config pyproject.toml src tests
