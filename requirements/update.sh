#!/bin/sh -e

# Options passed to this script are passed on to pip-compile. Therefore,
# dependencies can be upgraded to their latest version with:
#
#     ./requirements/update.sh -U

export CUSTOM_COMPILE_COMMAND=./requirements/update.sh

if python -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) else 1)'; then
  PY_VER=py3.12
elif python -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 10) else 1)'; then
  PY_VER=py3.10
else
  echo "This script must be run either on Python 3.10 (to generate the dependency" >&2
  echo "pinnings for Ubuntu 22.04) or Python 3.12 (to generate the dependency " >&2
  echo "pinnings for Ubuntu 24.04 or later)." >&2
  exit 1
fi

# --strip-extras is necessary because we use requirements/*.txt as PIP
# --constraint files (-c option)
python -m piptools compile \
       --allow-unsafe --strip-extras --resolver=backtracking \
       --output-file=requirements/${PY_VER}-production.txt "$@"
python -m piptools compile \
       --allow-unsafe --strip-extras --resolver=backtracking \
       --output-file=requirements/${PY_VER}-test.txt \
       requirements/${PY_VER}-test.in "$@"
