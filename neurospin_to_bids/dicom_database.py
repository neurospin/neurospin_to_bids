# -*- coding: utf-8 -*-

"""Tools for working with the NeuroSpin DICOM archive."""

import os.path

from .utils import UserError


NEUROSPIN_DATABASES = {
    'prisma': 'database/Prisma_fit',
    'trio': 'database/TrioTim',
    '7t': 'database/Investigational_Device_7T',
    'meg': 'neuromag/data',
}
"""Path of each scanner's database relative to /neurospin/acquisition."""


def get_database_path(scanner, acquisition_root_path='/neurospin/acquisition'):
    """Get the full path to the database corresponding to the given scanner.

    scanner (str): valid choices are the members of NEUROSPIN_DATABASES.keys()
    acquisition_root_path (str): normally '/neurospin/acquisition', but could
        be e.g. '/nfs/neurospin/acquisition' on a laptop.
    """
    try:
        relative_db_path = NEUROSPIN_DATABASES[scanner.strip().lower()]
    except KeyError:
        raise UserError('invalid scanner {0!r}, must be one of {{{1}}}'
                        .format(scanner,
                                ', '.join(NEUROSPIN_DATABASES.keys())))
    return os.path.join(acquisition_root_path, relative_db_path)


# Characters that are replaced by '-' in filenames (see the pdsu.py script in
# https://margaux.intra.cea.fr/redmine/projects/pdsu).
# illegal characters, to be filtered out from filenames:
# • Windows reserved characters
# • '_' because it is reserved by Brainvisa
# • spaces, tab, newline and null character
FILENAME_ILLEGAL_CHARS = '\\/:*?"<>|_ \t\r\n\0'
FILENAME_CLEANUP_TABLE = {ord(char): '-' for char in FILENAME_ILLEGAL_CHARS}
