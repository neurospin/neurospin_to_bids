#!/bin/sh -e

# Options passed to this script are passed on to pip-compile. Therefore,
# dependencies can be upgraded to their latest version with:
#
#     ./requirements/update.sh -U

export CUSTOM_COMPILE_COMMAND=./requirements/update.sh
# --strip-extras is necessary because we use requirements/*.txt as PIP
# --constraint files (-c option)
python -m piptools compile \
       --allow-unsafe --strip-extras --resolver=backtracking \
       --output-file=requirements/production.txt "$@"
python -m piptools compile \
       --allow-unsafe --strip-extras --resolver=backtracking \
       requirements/test.in "$@"

cat <<EOF >> requirements/test.txt

# Prevent 'pip-tools sync' from removing the neurospin-to-bids package...
neurospin-to-bids
EOF
