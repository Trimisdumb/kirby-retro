#!/usr/bin/env bash
# Kirby Retro Launcher — Linux / macOS
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"

if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "Python 3.10+ est requis. Installe-le (paquet python3), puis relance ./run.sh" >&2
  exit 1
fi

export PYTHONPATH="$DIR${PYTHONPATH:+:$PYTHONPATH}"
exec "$PY" -m retro_launcher "$@"
