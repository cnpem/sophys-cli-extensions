#!/usr/bin/env bash

set -e

eval "$(micromamba shell hook --shell bash)"
micromamba activate suitscase

pydm --hide-nav-bar --hide-menu-bar --hide-status-bar "$@"
