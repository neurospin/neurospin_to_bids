# -*- coding: utf-8 -*-
# Inspired by work by Soraya Brosset (2021), Pierre-Yves Postic (2022), and
# Aurélie Lebrun, 2021-2022.


"""Auto-listing of session contents by parsing the acquisition database."""


import csv
import fnmatch
import json
import logging
import os

import yaml

from . import acquisition_db
from . import bids
from . import exp_info


logger = logging.getLogger(__name__)


def autolist_dicom(exp_info_path):
    """Create participants_to_import.tsv using autolist rules.

    The list of subjects and sessions is read from participants_list.tsv. For
    each session, the DICOM session directory from /neurospin/acquisition is
    listed to obtain the list of (SequenceNumber, SequenceDescription), which
    are then matched against rules defined in autolist.yaml.

    Known limitation: duplicate BIDS names are not checked across different
    lines of the same subject and session.
    """
    filename = os.path.join(exp_info_path, 'participants_to_import.tsv')
    with open(filename, 'x', encoding='utf-8') as csv_file:
        writer = csv.DictWriter(csv_file, dialect=bids.BIDSTSVDialect,
                                fieldnames=exp_info.ALL_COLUMN_NAMES)
        writer.writeheader()
        for subject_info in _generate_autolist_dicom_lines(exp_info_path):
            subject_info['infos_participant'] = json.dumps(
                subject_info['infos_participant'])
            subject_info['to_import'] = json.dumps(
                subject_info['to_import'])
            writer.writerow(subject_info)


def _generate_autolist_dicom_lines(exp_info_path):
    with open(os.path.join(exp_info_path, 'autolist.yaml'), 'rb') as f:
        autolist_config = yaml.safe_load(f)
        # TODO validate the autolist config

    for subject_info in exp_info.iterate_participants_list(
            os.path.join(exp_info_path, 'participants_list.tsv')):
        logger.debug('Now autolisting:\n%s', subject_info)
        location = subject_info['location']
        acq_date = subject_info['acq_date'].strftime('%Y%m%d')
        nip = subject_info['NIP']
        session_dirs = acquisition_db.get_session_paths(
            location, acq_date, nip)
        if len(session_dirs) == 0:
            logger.error('no session directory found for NIP %s in %s', nip,
                         exp_info.get_session_paths(location, acq_date, nip))
        # Try to disambiguate multiple sessions automatically, by finding if
        # one of them has no match.
        to_import = []
        sessions_found = 0
        for session_dir in session_dirs:
            # TODO implement reading of to_import for manual overrides
            to_import_for_session = list(
                autolist_dicom_session(session_dir, autolist_config))
            if len(to_import_for_session) != 0:
                if sessions_found == 0:
                    to_import = to_import_for_session
                    nip = os.path.basename(session_dir)
                elif sessions_found == 1:
                    logger.error('multiple session directories match the '
                                 'given NIP %s: %s', subject_info['NIP'],
                                 session_dirs)
                    to_import = []
                sessions_found += 1
        subject_info['NIP'] = nip
        subject_info['to_import'] = to_import
        yield subject_info


def autolist_dicom_session(session_dir, autolist_config):
    """Generate rules for the to_import column for a given session."""
    series_list = sorted(acquisition_db.list_dicom_series(session_dir))
    logger.debug('List of DICOM series in %s: %s', session_dir, series_list)
    to_import = list(_autolist_dicom_first_pass(series_list, autolist_config))

    # TODO next pass: handle repetitions

    return to_import


def rule_matches(rule, series_description):
    return fnmatch.fnmatchcase(series_description, rule['SeriesDescription'])


def _autolist_dicom_first_pass(series_list, autolist_config):
    rules = autolist_config['rules']
    consecutive_series_rule = None
    consecutive_next_series_number = None  # to prevent F821 flake8 warning
    consecutive_next_order = None  # to prevent F821 flake8 warning
    for series_number, series_description in series_list:
        rule_matched = -1
        for rule_index, rule in enumerate(rules):
            if rule_matches(rule, series_description):
                logger.debug('rule %d matches series description %d (%s)',
                             rule_index, series_number, series_description)
                if rule_matched != -1:
                    logger.warning('in DICOM session %s, rules %d (%s) '
                                   'and %d (%s) both match series %d (%s), '
                                   'the first one takes precedence',
                                   rule_matched,
                                   rules[rule_matched]['SeriesDescription'],
                                   rule_index, rule['SeriesDescription'],
                                   series_number, series_description)
                    continue
                rule_matched = rule_index
                if (consecutive_series_rule is not None
                        and (consecutive_series_rule != rule_index
                             or (consecutive_next_series_number
                                 != series_number))):
                    logger.warning(
                        'Missing elements of the consecutive '
                        'series %d (%s): only %d/%d elements found',
                        consecutive_series_rule,
                        rules[consecutive_series_rule]['SeriesDescription'],
                        consecutive_next_order,
                        len(rules[consecutive_series_rule]
                            ['consecutive_series']),
                    )
                    consecutive_series_rule = None
                data_type = rule['data_type']
                metadata = rule.get('metadata')
                if 'bids_name' in rule:
                    bids_name = rule['bids_name']
                    assert consecutive_series_rule is None
                elif 'consecutive_series' in rule:
                    if consecutive_series_rule is not None:
                        assert consecutive_series_rule == rule_index
                        bids_name = (rule['consecutive_series']
                                     [consecutive_next_order]
                                     ['bids_name'])
                        consecutive_next_order += 1
                        consecutive_next_series_number += 1
                        if (consecutive_next_order
                                >= len(rule['consecutive_series'])):
                            consecutive_series_rule = None
                    else:
                        bids_name = rule['consecutive_series'][0]['bids_name']
                        consecutive_series_rule = rule_index
                        consecutive_next_order = 1
                        consecutive_next_series_number = series_number + 1
                else:
                    logger.error('ignoring malformed rule %d (%s): missing '
                                 'mandatory key bids_name or '
                                 'consecutive_series',
                                 rule_index, rule['SeriesDescription'])
                    rule_matched = -1

                logger.debug('first pass rule: %d -> %s/%s',
                             series_number, data_type, bids_name)
                if metadata:
                    yield (series_number, data_type, bids_name, metadata)
                else:
                    yield (series_number, data_type, bids_name)
