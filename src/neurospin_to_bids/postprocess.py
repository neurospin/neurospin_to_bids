# Author: Yann Leprince, 2022.
#
# Inspired by work by Soraya Brosset (2021), Pierre-Yves Postic (2022), and
# Aurélie Lebrun, 2021-2022.

"""Post-process the data converted by dcm2niix for full BIDS conformance."""


import collections
import glob
import itertools
import logging
import os
import re

from . import bids


logger = logging.getLogger(__name__)

# Recognize a filename with "postfixes" added by dcm2niix (_ph, _e1...)
BIDS_PLUS_POSTFIXES_RE = re.compile(r'^(?P<entities>([a-zA-Z0-9]+-[^_.]*_?)*)'
                                    r'_(?P<suffix>[a-zA-Z0-9]+)'
                                    r'_(?P<postfixes>[^.]+)'
                                    r'(?P<ext>\..*)$')

ECHO_POSTFIX_RE = re.compile(r'^e([0-9]+)$')


def rename_file_with_postfixes(filename, dry_run=False):
    dirname = os.path.dirname(filename)
    basename = os.path.basename(filename)
    match = BIDS_PLUS_POSTFIXES_RE.match(basename)
    if not match:
        return  # not a BIDS name with postfixes
    entities_list = []
    entities_text = match.group('entities').rstrip('_')
    if entities_text:
        for entity in entities_text.split('_'):
            key, value = entity.split('-', 1)
            entities_list.append((key, value))
    entities = collections.OrderedDict(entities_list)
    suffix = match.group('suffix')
    ext = match.group('ext')
    delete_file = False
    for postfix in match.group('postfixes').split('_'):
        echo_postfix_match = ECHO_POSTFIX_RE.match(postfix)
        if echo_postfix_match:
            try:
                echo_number = int(echo_postfix_match.group(1))
            except ValueError:
                logger.error('invalid echo number %s',
                             echo_postfix_match.group(1))
                return  # abort
            if suffix in ('magnitude', 'magnitude1', 'magnitude2'):
                suffix = f'magnitude{echo_number:d}'
                continue
            if suffix == 'phasediff' and echo_number == 2:
                continue
            formatted_echo_number = format(
                echo_number,
                '0{}d'.format(len(entities.get('echo', '0')))
                # TODO detect the maximum echo number in order to choose the
                # number of digits automatically
            )
            entities = bids.insert_entity(entities,
                                          'echo', formatted_echo_number)
        elif postfix == 'ph':
            # part-phase should already be in the filename, or a phase-related
            # suffix such as _phasediff.
            if suffix in ('phasediff', 'phase1', 'phase2', 'phase'):
                continue
            else:
                entities = bids.insert_entity(entities,
                                              'part', 'phase')
        elif postfix == 'real':
            entities = bids.insert_entity(entities, 'part', 'real')
        elif postfix == 'imaginary':
            entities = bids.insert_entity(entities, 'part', 'imag')
        elif postfix.startswith('ROI'):
            delete_file = True
            break
        else:
            logger.error('not fixing filename %s: unknown postfix %s',
                         filename, postfix)
            return

    if delete_file:
        logger.info('%s %s',
                    'dry-run: would delete' if dry_run else 'deleting',
                    filename)
        filename_json = filename[:-len(ext)] + '.json'
        os.unlink(filename)
        if os.path.isfile(filename_json):
            logger.info('%s %s',
                        'dry-run: would delete' if dry_run else 'deleting',
                        filename_json)
            if not dry_run:
                os.unlink(filename_json)
    else:
        new_basename = bids.compose_bids_name(entities, suffix, ext)
        logger.info('%s %s to %s',
                    'dry-run: would rename' if dry_run else 'renaming',
                    filename, new_basename)
        if not dry_run:
            os.rename(filename, os.path.join(dirname, new_basename))
        filename_json = filename[:-len(ext)] + '.json'
        if os.path.isfile(filename_json):
            new_basename_json = new_basename[:-len(ext)] + '.json'
            logger.info('%s %s to %s',
                        'dry-run: would rename' if dry_run else 'renaming',
                        filename_json, new_basename_json)
            if not dry_run:
                os.rename(filename_json, os.path.join(dirname,
                                                      new_basename_json))


def rename_files_recursively(bids_root_dir, dry_run=False):
    for filename in itertools.chain(
            glob.iglob(os.path.join(glob.escape(bids_root_dir),
                                    'sub-*', 'ses-*', '*', '*')),
            glob.iglob(os.path.join(glob.escape(bids_root_dir),
                                    'sub-*', '*', '*'))):
        if ((filename.endswith('.nii') or filename.endswith('.nii.gz'))
                and os.path.isfile(filename)):
            rename_file_with_postfixes(filename, dry_run=dry_run)
