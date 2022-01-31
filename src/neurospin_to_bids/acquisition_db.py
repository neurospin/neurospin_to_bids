# -*- coding: utf-8 -*-

"""Tools for working with the NeuroSpin DICOM archive."""

import glob
import os.path

from .utils import DataError, UserError


NEUROSPIN_DATABASES = {
    'prisma': 'database/Prisma_fit',
    'trio': 'database/TrioTim',
    '7t': 'database/Investigational_Device_7T',
    'meg': 'neuromag/data',
}
"""Path of each scanner's database relative to /neurospin/acquisition."""


ACQUISITION_ROOT_PATH = '/neurospin/acquisition'
"""Normally '/neurospin/acquisition' on a NeuroSpin workstation.

In some cases it may be changed globally, e.g. '/nfs/neurospin/acquisition' on
a laptop.
"""


def get_database_path(scanner):
    """Get the full path to the database corresponding to the given scanner.

    scanner (str): valid choices are the members of NEUROSPIN_DATABASES.keys()
    """
    try:
        relative_db_path = NEUROSPIN_DATABASES[scanner.strip().lower()]
    except KeyError:
        raise UserError('invalid scanner {0!r}, must be one of {{{1}}}'
                        .format(scanner,
                                ', '.join(NEUROSPIN_DATABASES.keys())))
    return os.path.join(ACQUISITION_ROOT_PATH, relative_db_path)


# Characters that are replaced by '-' in filenames (see the pdsu.py script in
# https://margaux.intra.cea.fr/redmine/projects/pdsu).
# illegal characters, to be filtered out from filenames:
# • Windows reserved characters
# • '_' because it is reserved by Brainvisa
# • spaces, tab, newline and null character
FILENAME_ILLEGAL_CHARS = '\\/:*?"<>|_ \t\r\n\0'
FILENAME_CLEANUP_TABLE = {ord(char): '-' for char in FILENAME_ILLEGAL_CHARS}


def get_session_path(scanner, acq_date, nip):
    """Get the path to the directory containg data from one acquisition session

    scanner (str): valid choices are the members of NEUROSPIN_DATABASES.keys()
    acq_date (str): the acquisition date in YYYYMMDD format
    nip (str): the subject's NIP (personal identification number), which may
        optionally be suffixed with the session number and StudyID for
        disambiguation.
    """
    db_path = get_database_path(scanner)
    if scanner.lower() == 'meg':
        return os.path.join(db_path, nip, acq_date)
    else:  # MRI
        date_dir = os.path.join(db_path, acq_date)
        nip_dirs = glob.glob(os.path.join(glob.escape(date_dir),
                                          glob.escape(nip) + '*'))
        if len(nip_dirs) == 1:
            return nip_dirs[0]
        elif len(nip_dirs) == 0:
            raise DataError(
                f"no directory found for given NIP {nip} in {date_dir}"
            )
        else:
            raise DataError(
                "multiple paths for given NIP {nip} in {date_dir}: "
                "[{dirs_found}] - please mention the session of the subject "
                "for this date after the NIP, 2 sessions for the same subject "
                "the same day are possible."
                .format(nip=nip, date_dir=date_dir,
                        dirs_found=", ".join(os.path.basename(dir)
                                             for dir in nip_dirs))
            )
