"""Code related to the exp_info directory (inputs of neurospin-to-bids)"""

import ast
import collections.abc
import csv
import datetime
import json
import logging
import os
import re

from . import bids
from . import utils
from .utils import UserError


logger = logging.getLogger(__name__)


NIP_RE = re.compile('^([a-z]{2}[0-9]{6})(_[0-9]+)?(_[0-9]+)?$')
# FIXME: MEG uses a different version of NIP, and maybe also includes the
# protocol in the nip (e.g. protocol/ab_123456)


class ValidationError(Exception):
    """Exception raised for malformed input data."""
    pass


def parse_bids_entity(entity_or_label, *, key):
    """Read a BIDS key-value entity, prefixing key- if necessary.

    The whole key-value entity is returned.

    ValidationError is raised if the key-value pair is invalid.
    """
    try:
        if entity_or_label.startswith(key + '-'):
            bids.validate_bids_label(entity_or_label[(len(key)+1):])
            return entity_or_label
        else:
            bids.validate_bids_label(entity_or_label)
            return key + '-' + entity_or_label
    except bids.BIDSError as exc:
        raise ValidationError(str(exc)) from exc


def validate_NIP(nip):
    """Validate a NIP or NIP_AcquisitionNumber_StudyID combination.

    ValidationError is raised if the value is invalid
    """
    if not NIP_RE.match(nip):
        raise ValidationError('Invalid NIP or NIP_AcquisitionNumber_StudyID '
                              'combination')


def parse_acq_date(date_str):
    """Parse the acquisition date from a string to a datetime.date object.

    The input string must use YYYY-MM-DD, YYYYMMDD, YY-MM-DD, or YYMMDD format.
    """
    date_str = date_str.replace('-', '')
    try:
        if len(date_str) == 8:
            year = int(date_str[:4])
        elif len(date_str) == 2:
            year = 2000 + int(date_str[:2])
        else:
            raise ValueError  # real exception below
        month = int(date_str[-4:-2])
        day = int(date_str[-2:])
        return datetime.date(year, month, day)
    except ValueError:
        raise ValidationError('invalid acq_date, must be in YYYY-MM-DD, '
                              'YYYYMMDD, or YYMMDD format')


def validate_to_import(to_import, deep=False):
    """Validate the list in the to_import column.

    Validation of each element within the list is deferred until the actual
    import process, unless `deep` is True.
    """
    if not isinstance(to_import, collections.abc.Collection):
        raise ValidationError("to_import must be a list")
    if deep:
        for value in to_import:
            validate_element_to_import(value)


def validate_element_to_import(value):
    """Validate one element of the to_import list."""
    if not isinstance(value, collections.abc.Sequence):
        raise ValidationError("each element of to_import must be a list or "
                              "tuple")
    if not 3 <= len(value) <= 4:
        raise ValidationError("each element of to_import must be of length 3 "
                              "or 4")
    if not isinstance(value[0], (str, int)):
        raise ValidationError("the first value of each element of to_import "
                              "must be a string (for MEG) or integer (for "
                              "MRI) (offending value is {!r})"
                              .format(value[0]))
    if not isinstance(value[1], str):
        raise ValidationError("the second value of each element of to_import "
                              "must be a string (offending value is {!r})"
                              .format(value[1]))
    if not isinstance(value[2], str):
        raise ValidationError("the third value of each element of to_import "
                              "must be a string (offending value is {!r})"
                              .format(value[2]))
    try:
        bids.validate_bids_partial_name(value[2])
        if len(value) > 3:
            bids.validate_metadata_dict(value)
    except bids.BIDSError as exc:
        raise ValidationError(str(exc)) from exc


MANDATORY_COLUMNS = [
    'NIP',
    'acq_date',
    'location',
]

ALL_COLUMN_NAMES = [
    'subject_label',
    'NIP',
    'infos_participant',
    'session_label',
    'acq_date',
    # 'acq_label',   ## part of acq_date, should we implement it again???
    'location',
    'to_import',
]


def find_participants_to_import_tsv(exp_info_path, strict=False):
    """Find participants_to_import.tsv, in the exp_info directory.

    - exp_info_path (str) is the path to the exp_info directory which normally
    contains participants_to_import.tsv
    """
    if not os.path.exists(exp_info_path):
        raise UserError('exp_info directory not found')
    if os.path.isfile(os.path.join(exp_info_path,
                                   'participants_to_import.tsv')):
        return os.path.join(exp_info_path, 'participants_to_import.tsv')
    elif os.path.isfile(os.path.join(exp_info_path, 'participants.tsv')):
        # Legacy name of participants_to_import.tsv
        return os.path.join(exp_info_path, 'participants.tsv')
    else:
        raise UserError('exp_info/participants_to_import.tsv not found')


def iterate_participants_list(filename, strict=False):
    """Read participants_to_import.tsv, returning each line as a dictionary.

    - filename (str) is the path to the participants_to_import.tsv
    file.
    """
    with open(filename, encoding='utf-8', newline='') as csv_file:
        reader = csv.DictReader(csv_file, dialect=bids.BIDSTSVDialect)

        # Special case for the first column, which contains the subject label,
        # regardless of its header (historical behaviour).
        for column in MANDATORY_COLUMNS:
            if column not in reader.fieldnames:
                raise UserError('missing column %s in %s', column, filename)
        subject_label_header = reader.fieldnames[0]
        if subject_label_header in set(ALL_COLUMN_NAMES) - {'subject_label'}:
            raise UserError('the first column of %s must contain the '
                            'subject label, not %s', filename,
                            subject_label_header)

        for row in reader:
            try:
                try:
                    # The new subject_label item must be first in the output
                    # OrderedDict, so we must recreate it.
                    new_row = collections.OrderedDict({
                        'subject_label': parse_bids_entity(
                            row[subject_label_header].strip(), key='sub')
                    })
                    new_row.update(row)
                    row = new_row
                except ValidationError as exc:
                    raise ValidationError(
                        f'invalid subject_label: {exc}') from exc
                if subject_label_header != 'subject_label':
                    del row[subject_label_header]

                row['NIP'] = row['NIP'].strip()
                try:
                    validate_NIP(row['NIP'])
                except ValidationError as exc:
                    # Warn but do not make it an error, because invalid NIPs
                    # (typos) may be present in the database
                    logger.warning('%s, line %d: %s', filename,
                                   reader.line_num, exc)

                if row.get('session_label'):
                    try:
                        row['session_label'] = parse_bids_entity(
                            row['session_label'].strip(), key='ses')
                    except ValidationError as exc:
                        raise ValidationError(
                            f'invalid session_label: {exc}') from exc

                try:
                    row['infos_participant'] = json.loads(
                        row.get('infos_participant', '{}'))
                except json.JSONDecodeError as exc:
                    raise ValidationError(
                        'malformed JSON in infos_participant:\n'
                        + utils.pinpoint_json_error(exc)
                    )
                if not isinstance(row['infos_participant'],
                                  collections.Mapping):
                    raise ValidationError(
                        'infos_participant must be a JSON object '
                        '(i.e. a key-value dictionary)'
                    )

                row['acq_date'] = parse_acq_date(row['acq_date'].strip())
                row['location'] = row['location'].strip()

                try:
                    row['to_import'] = ast.literal_eval(
                        row.get('to_import', '[]').strip())
                except (ValueError, TypeError, SyntaxError, MemoryError,
                        RecursionError) as exc:
                    raise ValidationError(
                        'cannot parse the to_import column: ' + str(exc))
                validate_to_import(row['to_import'])
            except ValidationError as exc:
                if strict:
                    raise UserError(f'in {filename}, line {reader.line_num}: '
                                    f'{exc}') from exc
                else:
                    logger.error('in %s, skipping line %d: %s', filename,
                                 reader.line_num, exc)
            else:
                yield row
