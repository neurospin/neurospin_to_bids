# -*- coding: utf-8 -*-

"""Code related to the exp_info directory (inputs of neurospin-to-bids)"""

import os

import pandas as pd

from .utils import UserError


def read_participants_to_import(exp_info_path, filename=None):
    """Load participants_to_import.tsv as a Pandas dataframe.

    - exp_info_path (str) is the path to the exp_info directory which normally
    contains participants_to_import.tsv

    - filename (str or None) is the name of the participants_to_import.tsv
    file. In the normal case this is None, and the two names are used by
    decreasing of priority: 'participants_to_import.tsv' or 'participants.tsv'
    (the old, deprecated name for that file).
    """
    if not os.path.exists(exp_info_path):
        raise UserError('exp_info directory not found')
    if os.path.isfile(os.path.join(exp_info_path,
                                   'participants_to_import.tsv')):
        participants_to_import = os.path.join(exp_info_path,
                                              'participants_to_import.tsv')
    elif os.path.isfile(os.path.join(exp_info_path, 'participants.tsv')):
        # Legacy name of participants_to_import.tsv
        participants_to_import = os.path.join(exp_info_path,
                                              'participants.tsv')
    else:
        raise UserError('exp_info/participants_to_import.tsv not found')
    return pd.read_csv(participants_to_import,
                       dtype=str,
                       sep='\t',
                       na_filter=False,
                       index_col=False)
