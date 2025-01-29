#!/bin/bash

set -e

cd "$(cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/.." &> /dev/null && pwd)"

if ! command -v coverage ; then
    pip install -r requirements-dev.txt
fi

coverage run --branch -m unittest discover -v -s tests
coverage report -m --skip-empty --omit='tests/**/*'