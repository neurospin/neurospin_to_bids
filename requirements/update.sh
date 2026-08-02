#!/bin/sh -e

# This script generates a uv lockfile for Python 3.10 and creates symlinks
# for Python 3.12 and 3.14 (matching the previous requirements.txt setup).
# Options passed to this script are forwarded to uv lock.
# Run with -U to upgrade all packages to latest versions.

# Get the directory where this script is located
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
REPO_ROOT=$(dirname "$SCRIPT_DIR")

# Store the absolute path to requirements directory
REQ_DIR="$REPO_ROOT/requirements"

echo "Generating lockfile for Python 3.10..."

# Use a temporary directory since uv lock always creates uv.lock in current dir
TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

cp "$REPO_ROOT/pyproject.toml" "$TMPDIR/"
cd "$TMPDIR"

# Generate lockfile for Python 3.10 (works across all >=3.10 versions)
# Use the Python version from the environment, or default to 3.10
GENERATED_WITH="${UV_PYTHON:-3.10}"
uv lock --python "$GENERATED_WITH" "$@"

# Move the lockfile to the requirements directory as uv-3.10.lock
mv uv.lock "$REQ_DIR/uv-3.10.lock"

# Create symlinks for Python 3.12 and 3.14 (matching previous setup)
cd "$REQ_DIR"
ln -sf uv-3.10.lock uv-3.12.lock
ln -sf uv-3.10.lock uv-3.14.lock

echo "Lockfile generated: $REQ_DIR/uv-3.10.lock"
echo "Symlinks created: uv-3.12.lock -> uv-3.10.lock, uv-3.14.lock -> uv-3.10.lock"
