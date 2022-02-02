# -*- coding: utf-8 -*-

"""Code related to the BIDS standard."""

import csv
import json
import logging
import re
import warnings


logger = logging.getLogger(__name__)


BIDS_BASENAME_RE = re.compile(r'^(?P<entities>[a-zA-Z0-9]+-[^_]+_)+'
                              r'(?P<suffix>[a-zA-Z0-9]+)(?P<ext>\..+)$')
BIDS_LABEL_RE = re.compile(r'^[a-zA-Z0-9]+$')


class BIDSError(Exception):
    """Exception raised for unparseable BIDS data."""
    pass


class BIDSWarning(Warning):
    """Warning raised for non-conforming BIDS data.

    Using a Warning allows to transform it into an Exception in strict mode.
    """
    pass


class BIDSTSVDialect(csv.Dialect):
    delimiter = '\t'
    quotechar = "'"
    quoting = csv.QUOTE_MINIMAL
    # doublequote is not explicitly specified by BIDS, but it cannot be
    # otherwise as BIDS does not define an escapechar.
    doublequote = True
    escapechar = None
    # We do not necessarily want to write using the Windows convention, but we
    # want both \r and \n to be quoted if they appear in a field, so setting
    # lineterminator to '\r\n' seems to be the only way.
    lineterminator = '\r\n'


def validate_bids_basename(name):
    """Verify if the base name of a BIDS file is well-formed.

    Only general checks are performed, i.e. that key-value entities, suffix,
    and file extension can be recognized. In particular, this function does not
    check the compatibility of entities with the provided suffix. Order of the
    entities is not checked at the moment, but may be added in the future.
    """
    match = BIDS_BASENAME_RE.match(name)
    if not match:
        raise BIDSError(f"the target file name {name} cannot be parsed "
                        f"according to BIDS".format(name))
    entities = match.group('entities')[:-1]  # strip trailing '_'
    for entity in entities.split('_'):
        key, value = entity.split('-', 1)
        if not BIDS_LABEL_RE.match(value):
            warnings.warn(f'value for the BIDS entity {entity} should contain '
                          'alphanumeric characters only', BIDSWarning)


def validate_bids_label(label):
    if not BIDS_LABEL_RE.match(label):
        raise BIDSError('A BIDS label must consist of alphanumeric '
                        'characters only')


def _validate_metadata_dict(value):
    """Validate the additional metadata in each element of to_import."""
    if not isinstance(value[3], dict):
        raise BIDSError("the fourth value of each element of to_import "
                        "must be a dictionary (offending value is {!r})"
                        .format(value[3]))
    try:
        json.dumps(value)
    except TypeError:
        raise BIDSError("the fourth value of each element of "
                        "to_import must be a JSON object (a python "
                        "dict with string keys and JSON-compatible "
                        "values)")
