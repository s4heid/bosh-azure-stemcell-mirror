#!/bin/bash

set -e

pip-compile --output-file=requirements.txt --strip-extras requirements.in
pip-compile --output-file=requirements-dev.txt --strip-extras requirements-dev.in
