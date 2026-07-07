#!/bin/bash

set -e

cd "$(cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/.." &> /dev/null && pwd)"

if ! command -v ruff ; then
    pip install -r requirements-dev.txt
fi

ruff check src tests
