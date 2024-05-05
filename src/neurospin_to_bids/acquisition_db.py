"""Tools for working with the NeuroSpin DICOM archive."""

import glob
import logging
import os.path

from .utils import DataError, UserError


logger = logging.getLogger()


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


def set_root_path(root_path):
    """Set the acquisition root path globally for the current process."""
    global ACQUISITION_ROOT_PATH
    ACQUISITION_ROOT_PATH = root_path


def get_database_path(scanner):
    """Get the full path to the database corresponding to the given scanner.

    scanner (str): valid choices are the members of NEUROSPIN_DATABASES.keys()
    """
    try:
        relative_db_path = NEUROSPIN_DATABASES[scanner.strip().lower()]
    except KeyError:
        scanners = ', '.join(NEUROSPIN_DATABASES.keys())
        raise UserError(f'invalid scanner {scanner!r}, must be one of {{{scanners}}}')
    return os.path.join(ACQUISITION_ROOT_PATH, relative_db_path)


# Characters that are replaced by '-' in filenames (see the pdsu.py script in
# https://margaux.intra.cea.fr/redmine/projects/pdsu).
# illegal characters, to be filtered out from filenames:
# • Windows reserved characters
# • '_' because it is reserved by Brainvisa
# • spaces, tab, newline and null character
FILENAME_ILLEGAL_CHARS = '\\/:*?"<>|_ \t\r\n\0'
FILENAME_CLEANUP_TABLE = {ord(char): '-' for char in FILENAME_ILLEGAL_CHARS}

GLOB_SPECIAL_CHARS = '*?[!]'
GLOB_CLEANUP_TABLE = {ord(char): '-'
                      for char in (set(FILENAME_ILLEGAL_CHARS)
                                   - set(GLOB_SPECIAL_CHARS))}


def canonicalize_filename(text):
    """Canonicalize a string by replacing illegal characters with '-'."""
    return text.translate(FILENAME_CLEANUP_TABLE)


def canonicalize_glob_pattern(pattern):
    """Canonicalize a glob pattern by replacing illegal characters with '-'."""
    return pattern.translate(GLOB_CLEANUP_TABLE)


def get_session_path(scanner, acq_date, nip):
    """Get the path to the directory containing data from one acquisition session

    scanner (str): valid choices are the members of NEUROSPIN_DATABASES.keys()
    acq_date (str): the acquisition date in YYYYMMDD format
    nip (str): the subject's NIP (personal identification number), which may
        optionally be suffixed with the session number and StudyID for
        disambiguation.
    """
    session_paths = get_session_paths(scanner, acq_date, nip)
    if len(session_paths) == 1:
        return session_paths[0]
    elif len(session_paths) == 0:
        raise DataError(
            f"no directory found for given NIP {nip} in {scanner} on "
            f"{acq_date}"
        )
    else:
        raise DataError(
            "multiple paths for given NIP {nip} in {scanner} on {acq_date}: "
            "[{dirs_found}] - please mention the session of the subject "
            "for this date after the NIP, 2 sessions for the same subject "
            "the same day are possible."
            .format(nip=nip, scanner=scanner, acq_date=acq_date,
                    dirs_found=", ".join(os.path.basename(dir)
                                         for dir in session_paths))
        )


def get_session_paths(scanner, acq_date, nip):
    """Get the path to the directory containing data from acquisition session(s)

    scanner (str): valid choices are the members of NEUROSPIN_DATABASES.keys()
    acq_date (str): the acquisition date in YYYYMMDD format
    nip (str): the subject's NIP (personal identification number), which may
        optionally be suffixed with the session number and StudyID for
        disambiguation.

    A list is returned, which can be of zero length if no such session can be
    found.
    """
    db_path = get_database_path(scanner)
    if scanner.lower() == 'meg':
        session_dir = os.path.join(db_path, nip, acq_date)
        if os.path.isdir(session_dir):
            return [session_dir]
        else:
            return []
    else:  # MRI
        date_dir = os.path.join(db_path, acq_date)
        return glob.glob(os.path.join(glob.escape(date_dir),
                                      glob.escape(nip) + '*'))


def list_dicom_series(session_dir):
    """Generator listing the DICOM series in a given session directory.

    Each series is returned as a (SeriesNumber, SeriesDescription) pair. The
    SeriesDescription is extracted from the directory name, and canonicalized
    using canonicalize_filename(). The series are returned in no particular
    order.
    """
    for directory in os.listdir(session_dir):
        try:
            series_number, series_description = directory.split('_', 1)
        except ValueError:
            logger.warning('invalid series directory name %s', directory)
        series_number = int(series_number)
        series_description = canonicalize_filename(series_description)
        yield (series_number, series_description)
