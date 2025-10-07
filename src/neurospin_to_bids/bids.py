"""Code related to the BIDS standard."""

import collections
import csv
import itertools
import json
import logging
import re
import warnings

logger = logging.getLogger(__name__)


# Information below is based on this version of BIDS
BIDS_SPEC_VERSION = '1.8.0'

BIDS_PARTIAL_NAME_RE = re.compile(
    r'(?P<entities>((^|_)[a-zA-Z0-9]+-.*?)*)'
    r'(^|_|$)(?P<suffix>[a-zA-Z0-9]+)?'
    r'(?P<ext>\..+)?$'
)
BIDS_ENTITY_SPLIT_RE = re.compile(r'(?:^|_)([a-zA-Z0-9]+-)')
BIDS_LABEL_RE = re.compile(r'^[a-zA-Z0-9]+$')

# See https://github.com/bids-standard/bids-specification/blob/master/src/
# schema/rules/entities.yaml
BIDS_ENTITY_ORDER = [
    'sub',
    'ses',
    'sample',
    'task',
    'acq',
    'ce',
    'trc',
    'stain',
    'rec',
    'dir',
    'run',
    'mod',
    'echo',
    'flip',
    'inv',
    'mt',
    'part',
    'proc',
    'hemi',
    'space',
    'split',
    'recording',
    'chunk',
    'atlas',
    'res',
    'den',
    'label',
    'desc',
]


class BIDSError(Exception):
    """Exception raised for unparsable BIDS data."""

    pass


class BIDSWarning(Warning):
    """Warning raised for non-conforming BIDS data.

    Using a Warning allows to transform it into an Exception in strict mode.
    """

    pass


class BIDSTSVDialect(csv.Dialect):
    delimiter = '\t'
    quotechar = '"'
    quoting = csv.QUOTE_MINIMAL
    # doublequote is not explicitly specified by BIDS, but it cannot be
    # otherwise as BIDS does not define an escapechar.
    doublequote = True
    escapechar = None
    # We do not necessarily want to write using the Windows convention, but we
    # want both \r and \n to be quoted if they appear in a field, so setting
    # lineterminator to '\r\n' seems to be the only way.
    lineterminator = '\r\n'


def validate_bids_partial_name(name):
    """Verify if the partial base name of a BIDS file is well-formed.

    The partial name must include at least the suffix. It may optionally
    include entities and a file extension.

    Only general checks are performed, i.e. that key-value entities, suffix,
    and file extension can be recognized. In particular, this function does not
    check the compatibility of entities with the provided suffix. Order of the
    entities is not checked at the moment, but may be added in the future.

    """
    entities, _suffix, _ext = parse_bids_name(name)
    for key, value in entities.items():
        if not BIDS_LABEL_RE.match(value):
            warnings.warn(
                f'value for the BIDS entity {key}-{value} should '
                'contain alphanumeric characters only',
                BIDSWarning,
            )


def parse_bids_entities(entities_text):
    """Parse BIDS entities, returning each (key, value) pair as a generator."""
    split_entities = BIDS_ENTITY_SPLIT_RE.split(entities_text)
    assert split_entities[0] == ''
    for key, value in itertools.zip_longest(
        split_entities[1::2], split_entities[2::2], fillvalue=''
    ):
        if key:
            assert key[-1] == '-'
            key = key[:-1]
            yield (key, value)


def parse_bids_name(name):
    """Parse any part of a BIDS basename (entities, suffix, extension)."""
    match = BIDS_PARTIAL_NAME_RE.match(name)
    if not match:
        raise BIDSError(
            f'the target file name {name} cannot be parsed according to BIDS'.format(
                name
            )
        )
    return (
        collections.OrderedDict(parse_bids_entities(match.group('entities'))),
        match.group('suffix') or '',
        match.group('ext') or '',
    )


def compose_bids_name(entities, suffix, ext):
    """Compose a BIDS name from a entities, suffix, and extension.

    entities can be of type collections.OrderedDict, or simply a list of (key,
    value) pairs. Beware that the entities are used in the order that they are
    provided. In particular, an unordered 'dict' (Python < 3.8) is not
    suitable and will raise an error.
    """
    # We actually want to test if 'entities' has an ordered type, but
    # Reversible is the closest that we have.
    assert isinstance(entities, collections.abc.Reversible)
    if isinstance(entities, collections.abc.Mapping):
        entities_items = entities.items()
    else:
        entities_items = entities
    name = '_'.join(f'{key}-{value}' for key, value in entities_items)
    if suffix:
        name += '_' + suffix
    if ext:
        name += ext
    return name


def validate_bids_label(label):
    if not BIDS_LABEL_RE.match(label):
        raise BIDSError(
            f'Invalid BIDS label {label!r}: must consist of '
            f'alphanumeric characters only (1 or more)'
        )


def validate_metadata_dict(value):
    """Validate the additional metadata in each element of to_import."""
    if not isinstance(value[3], dict):
        raise BIDSError(
            'the fourth value of each element of to_import '
            f'must be a dictionary (offending value is {value[3]!r})'
        )
    try:
        json.dumps(value)
    except TypeError:
        raise BIDSError(
            'the fourth value of each element of '
            'to_import must be a JSON object (a python '
            'dict with string keys and JSON-compatible '
            'values)'
        )


def add_entities(bids_basename, new_entities_str):
    """Add entities to a BIDS name."""
    entities, suffix, ext = parse_bids_name(bids_basename)
    new_entities, _, _ = parse_bids_name(new_entities_str)
    entities = set_entities(entities, new_entities)
    return compose_bids_name(entities, suffix, ext)


def set_entities(base_entities, new_entities, override_policy='override'):
    # TODO: ensure base_entities is an OrderedDicts
    # First pass: replace existing entity values
    for key, value in new_entities.items():
        if key in base_entities:
            if override_policy == 'override':
                pass
            elif override_policy == 'warn':
                logger.warning(
                    'replacing %s-%s with %s-%s', key, base_entities[key], key, value
                )
            elif override_policy == 'raise':
                raise RuntimeError(
                    f'entity {key} already exists and overriding is disabled'
                )
            else:
                raise ValueError('invalid value for override_policy')
            base_entities[key] = value
    # Second pass: add new entities
    entities_list = list(base_entities.items())
    for key, value in new_entities.items():
        insertion_pos = _find_insertion_position(entities_list, key)
        entities_list.insert(insertion_pos, (key, value))
    return collections.OrderedDict(entities_list)


def insert_entity(base_entities, key, value):
    return set_entities(base_entities, {key: value})


def _find_insertion_position(entity_list, key):
    try:
        key_index = BIDS_ENTITY_ORDER.index(key)
    except ValueError:
        return len(entity_list)  # insert unknown entities last
    # Look for the first key in entity_list that precedes the key, in the sense
    # of BIDS_ENTITY_ORDER, and return its index + 1.
    entity_list_keys = {k: i for i, (k, v) in enumerate(entity_list)}
    for candidate_key in reversed(BIDS_ENTITY_ORDER[:key_index]):
        if candidate_key in entity_list_keys:
            return entity_list_keys[candidate_key] + 1
    return 0
