#!/bin/sh -e

# This script generates locked dependency files using uv.
# Options passed to this script are forwarded to uv export.
# Run with -U to upgrade all packages to latest versions.

# Get the directory where this script is located
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
REPO_ROOT=$(dirname "$SCRIPT_DIR")

# Detect Python version to determine which files to generate
if python -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 10) else 1)'; then
  PY_VER=3.10
elif python -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) else 1)'; then
  PY_VER=3.12
elif python -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 14) else 1)'; then
  PY_VER=3.14
else
  echo "This script must be run with Python 3.10, 3.12, or 3.14" >&2
  exit 1
fi

echo "Generating requirements files for Python ${PY_VER}..."

# Use a temporary directory to avoid polluting the repo with uv.lock
TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

# Store the absolute path to requirements directory
REQ_DIR="$REPO_ROOT/requirements"

# Remove any symlinks so we can write actual files
rm -f "$REQ_DIR/py${PY_VER}-production.txt" "$REQ_DIR/py${PY_VER}-test.txt"

cp "$REPO_ROOT/pyproject.toml" "$TMPDIR/"
cd "$TMPDIR"

# Generate production requirements (no dev dependencies)
uv export --python "$PY_VER" --format requirements.txt --no-dev \
  -o "$REQ_DIR/py${PY_VER}-production.txt" "$@"

# Generate test requirements (includes production + dev dependencies)
# Note: The test.in file references production.txt as a constraint.
# For simplicity, we export all dependencies including dev group.
uv export --python "$PY_VER" --format requirements.txt --all-extras \
  -o "$REQ_DIR/py${PY_VER}-test.txt" "$@"

echo "Requirements files generated: $REQ_DIR/py${PY_VER}-production.txt $REQ_DIR/py${PY_VER}-test.txt"
