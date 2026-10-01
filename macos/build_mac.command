#!/bin/bash
set -eu
SCRIPT_DIR="$(cd -- "$(dirname "$0")" && pwd)"
PYTHON_COMMAND="${SOL_PYTHON:-python3.14}"
if ! command -v "$PYTHON_COMMAND" >/dev/null 2>&1; then
  echo "Python 3.14 was not found. Install Python 3.14 for this Mac, or set SOL_PYTHON to its executable path." >&2
  exit 1
fi
exec "$PYTHON_COMMAND" "$SCRIPT_DIR/build_mac.py" "$@"
