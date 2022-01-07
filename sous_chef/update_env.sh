#!/bin/bash
export PIP_REQUIRE_VIRTUALENV=false
export PYTHONPATH=$PYTHONPATH:$PWD
conda env update --file environment.yml
