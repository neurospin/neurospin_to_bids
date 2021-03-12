#!/bin/sh -e

# Options passed to this script are passed on to pip-compile. Therefore,
# dependencies can be upgraded to their latest version with:
#
#     ./requirements/update.sh -U

export CUSTOM_COMPILE_COMMAND=./requirements/update.sh
python -m piptools compile --allow-unsafe \
       --output-file=requirements/production.txt "$@"
python -m piptools compile --allow-unsafe requirements/test.in "$@"
