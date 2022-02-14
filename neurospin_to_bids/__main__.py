#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import collections.abc
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import time
from ast import literal_eval
from collections import OrderedDict
from itertools import combinations
from pathlib import Path

import mne
import numpy as np
import pandas as pd
import yaml
import pydeface.utils as pdu
from bids_validator import BIDSValidator
from mne_bids import make_dataset_description, write_raw_bids
import pkg_resources

from . import acquisition_db
from . import exp_info
from .utils import DataError, UserError


class Bcolors:
    """Colors to improve print statements' readability

    Example:
        `print(f"{Bcolors.OKBLUE}Hello World!{Bcolors.ENDC}")`
    """
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


NONINTERACTIVE = False


def yes_no(question: str, *,
           default: str = None, noninteractive: bool = None) -> bool:
    """A simple yes/no prompt

    Args:
        question (str): The question to be answered.
        default (bool, optional): Default answer to `question`.
                                  Defaults to None.

    Raises:
        ValueError: Raise `ValueError` when default answer is not
                    `yes` or `no`.

    Returns:
        bool: Boolean answer to the yes/no question.
    """
    valid = {"yes": True, "y": True, "no": False, "n": False}
    if NONINTERACTIVE:
        if noninteractive is not None:
            return noninteractive
        else:
            return valid[default]
    if default is None:
        prompt = " [y/n] "
    elif default == "yes":
        prompt = " [Y/n] "
    elif default == "no":
        prompt = " [y/N] "
    else:
        raise ValueError(f"invalid default answer: '{default}'")

    while True:
        choice = input(question + prompt).lower()
        if choice == '' and default is not None:
            return valid[default]
        if choice in valid:
            return valid[choice]
        print("Please respond with 'yes' or 'no' " "(or 'y' or 'n').\n")


def file_manager_default_file(main_path,
                              filter_list,
                              file_tag,
                              file_type='*',
                              allow_other_fields=True):
    """Path to the most specific file with respect to optional filters.

    Each filter is a list [key, value]. Like [sub, 01] or [ses, 02].

    Following BIDS standard files can be of the form
    [key-value_]...[key-value_]file_tag.file_type.
    """
    filters = []
    for n in reversed(range(1, len(filter_list) + 1)):
        filters += combinations(filter_list, n)
    filters += [[]]
    for filt in filters:
        found = get_bids_files(main_path,
                               sub_folder=False,
                               file_type=file_type,
                               file_tag=file_tag,
                               filters=filt,
                               allow_other_fields=allow_other_fields)
        if found:
            return found[0]
    return None


def file_reference(img_path):
    reference = {}
    reference['file_path'] = img_path
    reference['file_basename'] = os.path.basename(img_path)
    parts = reference['file_basename'].split('_')
    tag, typ = parts[-1].split('.', 1)
    reference['file_tag'] = tag
    reference['file_type'] = typ
    reference['file_fields'] = ''
    reference['fields_ordered'] = []
    for part in parts[:-1]:
        reference['file_fields'] += part + '_'
        field, value = part.split('-')
        reference['fields_ordered'].append(field)
        reference[field] = value
    return reference


def get_bids_files(main_path,
                   file_tag='*',
                   file_type='*',
                   sub_id='*',
                   file_folder='*',
                   filters=None,
                   ref=False,
                   sub_folder=True,
                   allow_other_fields=True):
    """Return files following bids spec

    Filters are of the form (key, value). Only one filter per key allowed.
    A file for which a filter do not apply will be discarded.
    """
    if sub_folder:
        files = os.path.join(main_path, 'sub-*', 'ses-*')
        if glob.glob(files):
            files = os.path.join(
                main_path, 'sub-%s' % sub_id, 'ses-*', file_folder,
                'sub-%s*_%s.%s' % (sub_id, file_tag, file_type))
        else:
            files = os.path.join(
                main_path, 'sub-%s' % sub_id, file_folder,
                'sub-%s*_%s.%s' % (sub_id, file_tag, file_type))
    else:
        files = os.path.join(main_path, '*%s.%s' % (file_tag, file_type))

    files = glob.glob(files)
    files.sort()
    if filters:
        if not allow_other_fields:
            files = [
                file_ for file_ in files
                if len(os.path.basename(file_).split('_')) <= len(filters) + 1
            ]
        files = [file_reference(file_) for file_ in files]
        for key, value in filters:
            files = [
                file_ for file_ in files
                if (key in file_ and file_[key] == value)
            ]
    else:
        files = [file_reference(file_) for file_ in files]

    if ref:
        return files
    else:
        return [ref_file['file_path'] for ref_file in files]


def bids_copy_events(behav_path='exp_info/recorded_events',
                     data_root_path='',
                     dataset_name=None):
    dataset_name, data_path = get_bids_default_path(data_root_path,
                                                    dataset_name)
    # ~ print(os.path.join(data_root_path, behav_path, 'sub-*', 'ses-*'))
    if glob.glob(os.path.join(data_root_path, behav_path, 'sub-*', 'ses-*')):
        sub_folders = glob.glob(
            os.path.join(behav_path, 'sub-*', 'ses-*', 'func'))
    else:
        # ~ print(os.path.join(data_root_path, behav_path,'sub-*', 'func'))
        sub_folders = glob.glob(
            os.path.join(data_root_path, behav_path, 'sub-*', 'func'))

    # raise warning if no folder is found in recorded events
    if not sub_folders:
        print(
            f'{Bcolors.WARNING}BIDS IMPORT WARNING: NO EVENTS FILE{Bcolors.ENDC}'
        )
    else:
        for sub_folder in sub_folders:
            # ~ file_path = sub_folder.replace(behav_path + '/', '')
            file_path = sub_folder
            for file_name in os.listdir(os.path.join(sub_folder)):

                # ~ dest_directory = os.path.join(data_path, file_path)
                # ~ if not os.path.exists(dest_directory):
                # ~     os.makedirs(dest_directory)

                file_ext = []
                last = ''
                root, last = os.path.split(sub_folder)
                while last != 'recorded_events':
                    if last == '':
                        break
                    file_ext.append(last)
                    sub_folder = root
                    root, last = os.path.split(sub_folder)

                list_tmp = []
                elements_path = [[item, '/'] for item in reversed(file_ext)]
                elements_path = [(list_tmp.append(item[0]),
                                  list_tmp.append(item[1]))
                                 for item in elements_path]
                ext = ''.join(list_tmp)
                shutil.copyfile(os.path.join(file_path, file_name),
                                os.path.join(data_path, ext, file_name))


def get_bids_path(data_root_path='',
                  subject_id='01',
                  folder='',
                  session_id=None):
    if session_id is None:
        session_id = ''
    else:
        session_id = 'ses-' + session_id
    return os.path.join(data_root_path, 'sub-' + subject_id, session_id, folder)


def get_bids_file_descriptor(subject_id,
                             task_id=None,
                             session_id=None,
                             acq_label=None,
                             dir_label=None,
                             rec_id=None,
                             fa_id=None,
                             part_label=None,
                             echo_id=None,
                             run_id=None,
                             run_dir=None,
                             file_tag=None,
                             file_type=None):
    """ Creates a filename descriptor following BIDS.

    subject_id refers to the subject label
    task_id refers to the task label
    run_id refers to run index
    acq_label refers to acquisition parameters as a label
    rec_id refers to reconstruction parameters as a label
    part_label refers to magnitude and phase parts of the images
    echo_id refers to the index of the echo time
    fa_id refers to the index of the used flip angle
    """
    if 'sub-' or 'sub' in subject_id:
        descriptor = subject_id
    else:
        descriptor = 'sub-{0}'.format(subject_id)
    if (session_id is not None) and (session_id is not np.nan):
        descriptor += '_ses-{0}'.format(session_id)
    if (task_id is not None) and (task_id is not np.nan):
        descriptor += '_task-{0}'.format(task_id)
    if (acq_label is not None) and (acq_label is not np.nan):
        descriptor += '_acq-{0}'.format(acq_label)
    if (echo_id is not None) and (echo_id is not np.nan):
        descriptor += '_echo-{0}'.format(echo_id)
    if (part_label is not None) and (part_label is not np.nan):
        descriptor += '_part-{0}'.format(part_label)
    if (fa_id is not None) and (fa_id is not np.nan):
        descriptor += '_fa-{0}'.format(fa_id)
    if (dir_label is not None) and (dir_label is not np.nan):
        descriptor += '_dir-{0}'.format(dir_label)
    if (rec_id is not None) and (rec_id is not np.nan):
        descriptor += '_rec-{0}'.format(rec_id)
    if (run_dir is not None) and (run_dir is not np.nan):
        descriptor += '_dir-{0}'.format(run_dir)
    if (run_id is not None) and (run_id is not np.nan):
        descriptor += '_run-{0}'.format(run_id)
    if (file_tag is not None) and (file_type is not None):
        descriptor += '_{0}.{1}'.format(file_tag, file_type)
    return descriptor


def get_bids_default_path(data_root_path='', dataset_name=None):
    """Default experiment raw dataset folder name"""
    if dataset_name is None:
        dataset_name = 'rawdata'
    return (dataset_name, os.path.join(data_root_path, dataset_name))


def bids_init_dataset(data_root_path='',
                      dataset_name=None,
                      dataset_description=None,
                      readme='',
                      changes=''):
    """Create directories and files missing to follow bids.

    Files and folders already created will be left untouched.
    This is an utility to initialize all files that should be present
    according to the standard. Particularly those that should be filled
    manually like README files.

    dataset_description.json : interactif mode to fill in. Or later on if the
    user wants. By default :
    Name: dataset_name
    BidsVersion: 1.0.0

    README is quite free as a file

    CHANGES follow CPAN standards

    """

    # CHECK DATASET REPOSITORY
    dataset_name, dataset_name_path = get_bids_default_path(
        data_root_path, dataset_name)
    if not os.path.exists(dataset_name_path):
        os.makedirs(dataset_name_path)

    # CHECK dataset_description.json FILE
    description_file = os.path.exists(
        os.path.join(dataset_name_path, 'dataset_description.json'))
    overwrite_datadesc_file = True
    if description_file:
        overwrite_datadesc_file = yes_no(
            '\nA dataset_description.json already exists, do you want to overwrite?',
            default="yes")
    if overwrite_datadesc_file or not description_file:
        data_descrip = yes_no(
            '\nDo you want to create or overwrite the dataset_description.json?',
            default="yes", noninteractive=False)
        if data_descrip:
            print(
                '\nIf you do not know all information: pass and edit the file later.'
            )
            name = input("\nType the name of this BIDS dataset: ").capitalize()
            authors = input("\nA list of authors like `a, b, c`: ").capitalize()
            acknowledgements = input(
                "\nA list of acknowledgements like `a, b, c`: ").capitalize()
            how_to_acknowledge = input(
                "\nEither a str describing how to  acknowledge this dataset OR a list of publications that should be cited: "
            )
            funding = input(
                '\nList of sources of funding (e.g., grant numbers). Must be a list of strings or a single comma separated string like `a, b, c`: '
            )
            references_and_links = input(
                "\nList of references to publication that contain information on the dataset, or links. Must be a list of strings or a single comma separated string like `a, b, c`: "
            )
            doi = input('\nThe DOI for the dataset: ')
            make_dataset_description(dataset_name_path,
                                     name=name,
                                     data_license=None,
                                     authors=authors,
                                     acknowledgements=str(acknowledgements),
                                     how_to_acknowledge=how_to_acknowledge,
                                     funding=str(funding),
                                     references_and_links=references_and_links,
                                     doi=doi,
                                     verbose=False)
        else:
            print(
                "\nYou may update the README file later on. A README file by default has been created."
            )
            make_dataset_description(dataset_name_path, name=dataset_name)

    # CHECK CHANGES FILE / TEXT FILE CPAN CONVENTION
    changes_file = os.path.join(dataset_name_path, 'CHANGES')
    changes_file_exists = os.path.exists(changes_file)
    overwrite_changes_file = True
    if changes_file_exists:
        overwrite_changes_file = yes_no(
            '\nA CHANGES file already exists, do you want to overwrite?',
            default="yes")

    if overwrite_changes_file or not changes_file_exists:
        changes = yes_no('\nDo you want to create/overwrite the CHANGES file?',
                         default="yes", noninteractive=False)
        if changes:
            changes_input = input("Type your text: ")
            with open(changes_file, 'w', encoding="utf-8") as fid:
                fid.write(str(changes_input))

    # CHECK README FILE / TEXT FILE
    readme_file = os.path.join(os.path.join(dataset_name_path, 'README'))
    readme_file_exist = os.path.exists(readme_file)
    overwrite_readme_file = True
    if readme_file_exist:
        overwrite_readme_file = yes_no(
            '\nA README file already exists, do you want to overwrite?',
            default="yes")

    if overwrite_readme_file or not readme_file_exist:
        readme = yes_no('\nDo you want to create/complete the README file?',
                        default="yes", noninteractive=False)
        if not readme:
            readme_input = "TO BE COMPLETED BY THE USER"
        else:
            readme_input = input("Type your text: ")
        with open(readme_file, 'w') as fid:
            fid.write(readme_input)


def bids_acquisition_download(data_root_path='',
                              dataset_name=None,
                              force_download=False,
                              behav_path='exp_info/recorded_events',
                              copy_events=False,
                              deface=False,
                              no_gz=False,
                              dry_run=False):
    """Automatically download files from neurospin server to a BIDS dataset.

    Download-database is based on NeuroSpin server conventions.
    Options are 'prisma', 'trio' and custom path.
    Prisma db_path = '/neurospin/acquisition/database/Prisma_fit'
    Trio db_path = '/neurospin/acquisition/database/TrioTim'

    The bids dataset is created if necessary before download with some
    empty mandatory files to be filled like README in case they don't exist.

    The download depends on the file '[sub-*_][ses-*_]download.csv' contained
    in the folder 'exp_info'.

    NIP and acq date of the subjects will be taken automatically from
    exp_info/participants_to_import.tsv file that follows bids standard. The
    file will be copied in the dataset folder without the NIP column for
    privacy.

    Possible exceptions
    1) exp_info directory not found
    2) participants_to_import.tsv not found
    3) download files not found
    4) Acquisition directory in neurospin server not found
    5) There is more than one acquisition directory (Have to ask manip for
    extra digits for NIP, the NIP then would look like xxxxxxxx-ssss)
    6) Event file corresponding to downloaded bold.nii not found

    """

    ####################################
    # CHECK PATHS AND FILES
    ####################################
    exp_info_path = os.path.join(data_root_path, 'exp_info')

    # Determine target path with the name of dataset
    dataset_name, target_root_path = get_bids_default_path(
        data_root_path, dataset_name)

    # Create dataset directories and files if necessary
    bids_init_dataset(data_root_path, dataset_name)

    # Manage the report and download information
    download_report = ('download_report_'
                       + time.strftime("%d-%b-%Y-%H:%M:%S", time.gmtime())
                       + '.csv')
    report_path = os.path.join(data_root_path, 'report')
    if not os.path.exists(report_path):
        os.makedirs(report_path)
    download_report = open(os.path.join(report_path, download_report), 'w')
    # ~ report_line = '%s,%s,%s\n' % ('subject_id', 'session_id', 'download_file')
    # ~ download_report.write(report_line)
    list_imported = []
    list_already_imported = []
    list_warning = []

    # Create a dataFrame to store participant information
    # ~ df_participant = pd.DataFrame()
    # Dict for info participant
    # ~ list_all_participants = {}
    dic_info_participants = OrderedDict()

    # List for the bacth file for dc2nii_batch command
    infiles_dcm2nii = []

    # List for data to deface
    files_for_pydeface = []

    # Dict of descriptors to be added
    dict_descriptors = {}

    ####################################
    # GETTING INFORMATION TO DOWNLOAD
    ####################################

    # Download command for each subject/session
    # one line has the following information
    # participant_id / NIP / infos_participant / session_label / acq_date / location / to_import

    # Read the participants_to_import.tsv file for getting subjects/sessions to
    # download
    pop = exp_info.read_participants_to_import(exp_info_path)

    # ~ print(df_participant)

    for _unused_index, subject_info in pop.iterrows():
        subject_id = subject_info[0].strip()

        # Fill the partcipant information for the participants_to_import.tsv
        if subject_info.get('infos_participant', '').strip():
            info_participant = json.loads(
                subject_info['infos_participant'].strip())
        else:
            info_participant = {}
        if subject_id in dic_info_participants:
            existing_items = dic_info_participants[subject_id]
            # Existing items take precedence over new values
            info_participant.update(existing_items)
        dic_info_participants[subject_id] = info_participant

        # sub_path = target_root_path + subject_id + ses_path
        # Mange the optional filters
        # optional_filters = [('sub', subject_id)]
        # if session_id is not None:
        #  optional_filters += [('ses', session_id)]
        if subject_info.get('session_label', '').strip():
            session_id = subject_info['session_label'].strip()
        else:
            session_id = None
        if session_id is None:
            ses_path = ''
        else:
            ses_path = 'ses-' + session_id

        if subject_id.isnumeric():
            int(subject_id)
            subject_id = 'sub-{0}'.format(subject_id)
        else:
            if 'sub-' not in subject_id:
                print(
                    f'{Bcolors.WARNING}BIDS IMPORTATION WARNING: SUBJECT ID PROBABLY NOT CONFORM{Bcolors.ENDC}'
                )

        sub_path = os.path.join(target_root_path, subject_id, ses_path)
        if not os.path.exists(sub_path):
            os.makedirs(sub_path)

        # Avoid redownloading subjects/sessions
        if not force_download:
            check_file = os.path.join(sub_path, 'downloaded')
            if os.path.isfile(check_file):
                continue

        # DATE has to be transformed from BIDS to NeuroSpin server standard
        # NeuroSpin standard is yyyymmdd -> Bids standard is YYYY-MM-DD
        acq_date = subject_info['acq_date'].strip().replace('-', '')

        # nip number
        nip = subject_info['NIP'].strip()

        # Get appropriate download file. As specific as possible
        # ~ specs_path = file_manager_default_file(exp_info_path,
        # ~                                        optional_filters, 'download',
        # ~                                        file_type='tsv',
        # ~                                        allow_other_fields=False)
        # ~ report_line = '%s,%s,%s\n' % (subject_id, session_id, specs_path)
        # ~ download_report.write(report_line)

        # ~ specs = pd.read_csv(specs_path, dtype=str, sep='\t', index_col=False)

        # Retrieve list of list for seqs to import
        # One tuple is configured as :(file_to_import;acq_folder;acq_name)
        # value[0] : num of seq
        # value[1] : modality
        # value[2] : part of ht file_name
        to_import = subject_info['to_import'].strip()
        if to_import:
            seqs_to_retrieve = literal_eval(to_import)
            if not isinstance(seqs_to_retrieve, collections.abc.Collection):
                raise TypeError("seqs_to_retrieve must be a Collection")
        else:
            seqs_to_retrieve = []
        print("Scans for ", nip)
        print(json.dumps(seqs_to_retrieve))
        # Convert the first element if there is only one sequence, otherwise
        # each value will be used as str and note tuple).
        if len(seqs_to_retrieve) > 0 and isinstance(seqs_to_retrieve[0], str):
            seqs_to_retrieve = [seqs_to_retrieve]

        # download data, store information in batch files for anat/fmri
        # download data for meg data
        for value in seqs_to_retrieve:
            # ~ print(seqs_to_retrieve)
            def get_value(key, text):
                m = re.search(key + '-(.+?)_', text)
                if m:
                    return m.group(1)
                else:
                    return None

            run_task = get_value('task', value[2])
            acq_label = get_value('acq', value[2])
            run_id = get_value('run', value[2])
            run_dir = get_value('dir', value[2])
            echo_id = get_value('echo', value[2])
            part_label = get_value('part', value[2])
            fa_id = get_value('fa', value[2])
            run_session = session_id

            tag = value[2].split('_')[-1]

            target_path = os.path.join(sub_path, value[1])
            if not os.path.exists(target_path):
                os.makedirs(target_path)

            # MEG CASE
            if value[1] == 'meg':
                # Create subject path if necessary
                meg_path = os.path.join(sub_path, 'meg')
                if not os.path.exists(meg_path):
                    os.makedirs(meg_path)

                # Create the sub-emptyroom
                # ~ sub-emptyroom_path = os.path.join(data_root_path, 'sub_emptyroom')
                # ~ if not os.path.exists(sub-emptyroom_path):
                    # ~ os.makedirs(sub-emptyroom_path)

                meg_file = os.path.join(
                    acquisition_db.get_database_path(subject_info['location']),
                    nip, acq_date, value[0]
                )
                print(meg_file)
                filename = get_bids_file_descriptor(subject_id,
                                                    task_id=run_task,
                                                    run_id=run_id,
                                                    run_dir=run_dir,
                                                    session_id=run_session,
                                                    file_tag=tag,
                                                    acq_label=acq_label,
                                                    echo_id=echo_id,
                                                    part_label=part_label,
                                                    fa_id=fa_id,
                                                    file_type='tif')
                # ~ output_path = os.path.join(target_path, filename)
                # ~ print(output_path)
                # ~ shutil.copyfile(meg_file, output_path)
                raw = mne.io.read_raw_fif(meg_file, allow_maxshield=True)

                write_raw_bids(raw, filename, target_path, overwrite=True)
                # add event
                # create json file
                # copy the subject emptyroom

            # ANAT and FUNC case
            # todo: bad practices, to refactor for the sake of simplicity
            elif value[1] in ('anat', 'func', 'dwi', 'fmap'):
                download = True
                dicom_paths = []
                path_file_glob = ""
                try:
                    nip_dir = acquisition_db.get_session_path(
                        subject_info['location'], acq_date, nip)
                except DataError as exc:
                    list_warning.append(str(exc))
                    download = False
                    continue
                path_file_glob = os.path.join(
                    nip_dir, '{0:06d}_*'.format(int(value[0])))
                # ~ print(path_file_glob)
                dicom_paths = glob.glob(path_file_glob)

                if not dicom_paths and download:
                    list_warning.append("file not found "
                                        + path_file_glob)
                    # ~ print(message)
                    # ~ download_report.write(message)
                elif download:
                    dicom_path = dicom_paths[0]
                    list_imported.append("\n IMPORTATION OF " + dicom_path)
                    # ~ print(message)
                    # ~ download_report.write(message)
                    # Expecting page 10 bids specification file name
                    filename = get_bids_file_descriptor(subject_id,
                                                        task_id=run_task,
                                                        run_id=run_id,
                                                        run_dir=run_dir,
                                                        session_id=run_session,
                                                        file_tag=tag,
                                                        acq_label=acq_label,
                                                        echo_id=echo_id,
                                                        part_label=part_label,
                                                        fa_id=fa_id,
                                                        file_type='nii')

                    if value[1] == 'anat' and deface:
                        print("\n Deface with pydeface")
                        files_for_pydeface.append(
                            os.path.join(target_path, filename))

                    # append list for preparing the batch importation
                    file_to_convert = {
                        'in_dir': dicom_path,
                        'out_dir': target_path,
                        'filename': os.path.splitext(filename)[0]
                    }
                    is_file_to_import = os.path.join(
                        os.path.join(os.getcwd(), target_path, filename))

                    if os.path.isfile(is_file_to_import):
                        list_already_imported.append(
                            f" ALREADY IMPORTED: {is_file_to_import}")
                    else:
                        infiles_dcm2nii.append(file_to_convert)

                    # Add descriptor into the json file
                    if run_task:
                        filename_json = os.path.join(target_path,
                                                     filename[:-3] + 'json')
                        dict_descriptors.update(
                            {filename_json: {
                                'TaskName': run_task
                            }})

                    if len(value) == 4:
                        # ~ print('value[3]', value[3] )
                        filename_json = os.path.join(target_path,
                                                     filename[:-3] + 'json')
                        dict_descriptors.update({filename_json: value[3]})

        # Importation and conversion of dicom files
        dcm2nii_batch = dict(Options=dict(isGz=(not no_gz),
                                          isFlipY=True,  # default is True
                                          isVerbose=False,
                                          isCreateBIDS=True,
                                          isOnlySingleFile=False),
                             Files=infiles_dcm2nii)

    dcm2nii_batch_file = os.path.join(exp_info_path, 'batch_dcm2nii.yaml')
    with open(dcm2nii_batch_file, 'w') as f:
        yaml.dump(dcm2nii_batch, f)

    print(
        "\n------------------------------------------------------------------------------------"
    )
    print(
        "-------------------    SUMMARY OF IMPORTATION   --------------------------------------"
    )
    print(
        "--------------------------------------------------------------------------------------\n"
    )
    for i in list_already_imported:
        print(i)
        download_report.write(i)
    print(
        "\n------------------------------------------------------------------------------------"
    )
    for i in list_imported:
        print(i)
        download_report.write(i)
    print(
        "\n------------------------------------------------------------------------------------"
    )
    print(Bcolors.WARNING, end='')
    for i in list_warning:
        print('\n  WARNING: ' + i)
        download_report.write('\n  WARNING: ' + i)
    print(Bcolors.ENDC)
    print(
        "------------------------------------------------------------------------------------"
    )
    print(
        "------------------------------------------------------------------------------------\n"
    )
    download_report.close()

    if dry_run:
        print("\n NO IMPORTATION, DRY-RUN OPTION IS TRUE \n")
    else:
        print('\n')
        cmd = ("dcm2niibatch", dcm2nii_batch_file)
        ret = subprocess.call(cmd)
        if ret != 0:
            print(f'{Bcolors.FAIL}dcm2niibatch returned an error, see above'
                  f'{Bcolors.ENDC}')

        # loop for checking if downloaded are ok and create the downloaded files
        #    done_file = open(os.path.join(sub_path, 'downloaded'), 'w')
        #    done_file.close()

        # Data to deface
        # ~ print(files_for_pydeface)
        if files_for_pydeface:
            try:
                # warning: Isn't that too restrictive?
                template = pkg_resources.resource_filename(
                    pkg_resources.Requirement.parse("neurospin_to_bids"),
                    "neurospin_to_bids/template_deface/mean_reg2mean.nii.gz")
                facemask = pkg_resources.resource_filename(
                    pkg_resources.Requirement.parse("neurospin_to_bids"),
                    "neurospin_to_bids/template_deface/facemask.nii.gz")
            except pkg_resources.DistributionNotFound:
                template = (
                    "/neurospin/unicog/protocols/IRMf/Unicogfmri/BIDS/"
                    "unicog-dev/bids/template_deface/mean_reg2mean.nii.gz")
                facemask = ("/neurospin/unicog/protocols/IRMf/Unicogfmri/BIDS/"
                            "unicog-dev/bids/template_deface/facemask.nii.gz")
            print(template)
            os.environ['FSLDIR'] = "/i2bm/local/fsl/bin/"
            os.environ['FSLOUTPUTTYPE'] = "NIFTI_PAIR"
            os.environ['PATH'] = os.environ['FSLDIR'] + ":" + os.environ['PATH']

            for file_to_deface in files_for_pydeface:
                print(f"\nDeface with pydeface {file_to_deface}")
                pdu.deface_image(infile=file_to_deface,
                                 outfile=file_to_deface,
                                 facemask=facemask,
                                 template=template,
                                 force=True)

        # Create participants.tsv in dataset folder (take out NIP column)
        participants_path = os.path.join(target_root_path, 'participants.tsv')
        df_participant = pd.DataFrame.from_dict(dic_info_participants,
                                                orient="index")
        df_participant.index.rename('participant_id', inplace=True)
        df_participant.to_csv(participants_path, sep='\t', na_rep="n/a")

        if dict_descriptors:
            # ~ print(dict_descriptors)
            # Adding a new key value pair in a json file such as taskname
            for k, v in dict_descriptors.items():
                with open(k, 'r+') as json_file:
                    for key, val in v.items():
                        temp_json = json.load(json_file)
                        temp_json[key] = val
                        json_file.seek(0)
                        json.dump(temp_json, json_file)
                        json_file.truncate()

        # Copy recorded event files
        if copy_events:
            bids_copy_events(behav_path, data_root_path, dataset_name)

        # Validate paths with BIDSValidator
        # see also http://bids-standard.github.io/bids-validator/
        validation_bids = yes_no('\nDo you want to use a bids validator?',
                                 default=None, noninteractive=False)
        if validation_bids:
            bids_validation_report = os.path.join(report_path,
                                                  "report_bids_valisation.txt")
            if shutil.which('bids-validator'):
                cmd = f"bids-validator {target_root_path} > {bids_validation_report}"
                subprocess.call(cmd, shell=True)
                cmd = f"cat < {bids_validation_report}"
                subprocess.call(cmd, shell=True)
                print(
                    f'\n\nSee the summary of bids validator at {bids_validation_report}'
                )
            else:
                validator = BIDSValidator()
                os.chdir(target_root_path)
                for file_to_test in Path('.').glob('./**/*'):
                    if file_to_test.is_file():
                        file_to_test = '/' + str(file_to_test)
                        print(
                            f'\nTest the following name of file : {file_to_test} with BIDSValidator'
                        )
                        print(validator.is_bids(file_to_test))

    print('\n')


def main(argv=sys.argv):
    global NONINTERACTIVE
    if sys.version_info < (3, 6):
        print('ERROR: neurospin_to_bids needs Python 3.6 or later')
        return 1
    # Parse arguments from console
    parser = argparse.ArgumentParser(description='NeuroSpin to BIDS conversion')
    parser.add_argument('--root-path', '-root_path',
                        default='.',
                        help='directory containing exp_info to download into')
    parser.add_argument('--dataset-name', '-dataset_name',
                        type=str,
                        default='rawdata',
                        help='name of the directory created in ROOT_PATH')
    parser.add_argument('--copy-events', '-copy_events',
                        action='store_true',
                        help='copy events from a directory with the same '
                        'structure')
    parser.add_argument('--acquisition-dir',
                        default='/neurospin/acquisition',
                        help='path to the NeuroSpin acquisition archive '
                        '[default: /neurospin/acquisition]')
    parser.add_argument('--no-gz', action='store_true',
                        help='Disable gzip compression of the Nifti output')
    parser.add_argument('--dry-run', '-n', '-dry-run',
                        action='store_true',
                        help='Test without importation of data')
    parser.add_argument('--noninteractive', action='store_true',
                        help='Do not request interactive input from the '
                        'terminal')

    # LOAD CONSOLE ARGUMENTS
    args = parser.parse_args(argv[1:])
    NONINTERACTIVE = args.noninteractive
    acquisition_db.ACQUISITION_ROOT_PATH = args.acquisition_dir
    deface = yes_no('\nDo you want deface T1?', default=None,
                    noninteractive=False)
    try:
        return bids_acquisition_download(data_root_path=args.root_path,
                                         dataset_name=args.dataset_name,
                                         force_download=False,
                                         behav_path='exp_info/recorded_events',
                                         copy_events=args.copy_events,
                                         deface=deface,
                                         no_gz=args.no_gz,
                                         dry_run=args.dry_run) or 0
    except UserError as exc:
        print('USER ERROR, aborting: {0}'.format(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
