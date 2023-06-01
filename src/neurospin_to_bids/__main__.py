#! /usr/bin/env python3

import argparse
import glob
import json
import logging
import os
import shlex
import shutil
import subprocess
import sys
import time
from collections import OrderedDict
from pathlib import Path

import mne
import pandas as pd
import yaml
import pydeface.utils as pdu
from bids_validator import BIDSValidator
from mne_bids import make_dataset_description, write_raw_bids
import pkg_resources

from . import acquisition_db
from . import bids
from . import exp_info
from . import postprocess
from . import utils
from .utils import DataError, UserError, yes_no


logger = logging.getLogger(__name__)


def bids_copy_events(behav_path='exp_info/recorded_events',
                     data_root_path='',
                     dataset_name=None):
    dataset_name, data_path = get_bids_default_path(data_root_path,
                                                    dataset_name)
    if glob.glob(os.path.join(data_root_path, behav_path, 'sub-*', 'ses-*')):
        sub_folders = glob.glob(
            os.path.join(behav_path, 'sub-*', 'ses-*', 'func'))
    else:
        sub_folders = glob.glob(
            os.path.join(data_root_path, behav_path, 'sub-*', 'func'))

    # raise warning if no folder is found in recorded events
    if not sub_folders:
        logger.warning('no events file')
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
            '\nA dataset_description.json already exists, do you want to '
            'overwrite?', default="yes")
    if overwrite_datadesc_file or not description_file:
        data_descrip = yes_no('\nDo you want to create or overwrite the '
                              'dataset_description.json?',
                              default="yes", noninteractive=False)
        if data_descrip:
            print('\nIf you do not know all information: skip and edit the '
                  'file later on.')
            name = input("\nType the name of this BIDS dataset: ")
            authors = input("\nA list of authors like `a, b, c`: ")
            acknowledgements = input(
                "\nA list of acknowledgements like `a, b, c`: ")
            how_to_acknowledge = input(
                "\nEither a str describing how to  acknowledge this dataset "
                "OR a list of publications that should be cited: "
            )
            funding = input(
                '\nList of sources of funding (e.g., grant numbers). Must be '
                'a list of strings or a single comma separated string like '
                '`a, b, c`: '
            )
            references_and_links = input(
                "\nList of references to publication that contain information "
                "on the dataset, or links. Must be a list of strings or a "
                "single comma separated string like `a, b, c`: "
            )
            doi = input('\nThe DOI for the dataset: ')
            make_dataset_description(path=dataset_name_path,
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
            print("\nYou may update the README file later on. A README file "
                  "has been created with dummy contents.")
            make_dataset_description(path=dataset_name_path, name=dataset_name)

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
                              data_orientation='default',
                              dry_run=False):
    """Automatically download files from neurospin server to a BIDS dataset.

    Download-database is based on NeuroSpin server conventions.
    Options are 'prisma', 'trio' and custom path.
    Prisma db_path = '/neurospin/acquisition/database/Prisma_fit'
    Trio db_path = '/neurospin/acquisition/database/TrioTim'

    The bids dataset is created if necessary before download with some
    empty mandatory files to be filled like README in case they don't exist.

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
    _, sourcedata_path = get_bids_default_path(data_root_path, 'sourcedata')

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
    # ~ report_line = '%s,%s,%s\n' % ('subject_id', 'session_id',
    # ~                               'download_file')
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

    gz_ext = '' if no_gz else '.gz'

    ####################################
    # GETTING INFORMATION TO DOWNLOAD
    ####################################

    # Download command for each subject/session
    # one line has the following information
    # participant_id / NIP / infos_participant / session_label / acq_date /
    # location / to_import

    # Read the participants_to_import.tsv file for getting subjects/sessions to
    # download
    pti_filename = exp_info.find_participants_to_import_tsv(exp_info_path)
    for subject_info in exp_info.iterate_participants_list(pti_filename):
        logger.debug('Now handling:\n%s', subject_info)
        sub_entity = subject_info['subject_label']
        ses_entity = subject_info.get('session_label', '')

        # Fill the partcipant information for the participants_to_import.tsv
        info_participant = subject_info['infos_participant']
        if sub_entity in dic_info_participants:
            existing_items = dic_info_participants[sub_entity]
            # Existing items take precedence over new values
            info_participant.update(existing_items)
        dic_info_participants[sub_entity] = info_participant

        sub_path = os.path.join(target_root_path, sub_entity, ses_entity)
        sourcedata_sub_path = os.path.join(sourcedata_path,
                                           sub_entity, ses_entity)
        if not os.path.exists(sub_path):
            os.makedirs(sub_path)

        # Avoid redownloading subjects/sessions
        if not force_download:
            check_file = os.path.join(sub_path, 'downloaded')
            if os.path.isfile(check_file):
                continue

        # Date in format used by /neurospin/acquisition: YYYYMMDD
        acq_date = subject_info['acq_date'].strftime('%Y%m%d')

        # nip number
        nip = subject_info['NIP']

        # Retrieve list of list for seqs to import
        # One tuple is configured as :(file_to_import;acq_folder;acq_name)
        # value[0] : num of seq
        # value[1] : modality
        # value[2] : part of ht file_name
        seqs_to_retrieve = subject_info['to_import']
        logger.debug("to_import for %s on %s: %s", nip, acq_date,
                     json.dumps(seqs_to_retrieve))
        # Convert the first element if there is only one sequence, otherwise
        # each value will be used as str and note tuple).
        if len(seqs_to_retrieve) > 0 and isinstance(seqs_to_retrieve[0], str):
            seqs_to_retrieve = [seqs_to_retrieve]

        # download data, store information in batch files for anat/fmri
        # download data for meg data
        for value in seqs_to_retrieve:
            try:
                exp_info.validate_element_to_import(value)
            except exp_info.ValidationError as exc:
                logger.error('for subject %s on %s, skipping import of a '
                             'sequence: %s', nip, acq_date, str(exc))

            target_path = os.path.join(sub_path, value[1])
            sourcedata_target_path = os.path.join(sourcedata_sub_path,
                                                  value[1])
            if not os.path.exists(target_path):
                os.makedirs(target_path)

            target_filename = bids.add_entities(value[2],
                                                sub_entity + '_' + ses_entity)

            # MEG CASE
            if value[1] == 'meg':
                # Create subject path if necessary
                meg_path = os.path.join(sub_path, 'meg')
                if not os.path.exists(meg_path):
                    os.makedirs(meg_path)

                meg_file = os.path.join(
                    acquisition_db.get_database_path(subject_info['location']),
                    nip, subject_info['acq_date'].strftime('%y%m%d'), value[0]
                )
                logger.info(meg_file)

                raw = mne.io.read_raw_fif(meg_file, allow_maxshield=True)

                write_raw_bids(raw, target_filename, target_path,
                               overwrite=True)
                # add event
                # create json file
                # copy the subject emptyroom

            # MRI CASE
            # todo: bad practices, to refactor for the sake of simplicity
            else:
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
                    nip_dir, f'{int(value[0]):06d}_*')
                dicom_paths = glob.glob(path_file_glob)

                if not dicom_paths and download:
                    list_warning.append("file not found "
                                        + path_file_glob)
                elif download:
                    dicom_path = dicom_paths[0]
                    list_imported.append("importation of " + dicom_path)

                    if value[1] == 'anat' and deface:
                        logger.info("\n Deface with pydeface")
                        files_for_pydeface.append(
                            os.path.join(target_path,
                                         target_filename + '.nii' + gz_ext))

                    # append list for preparing the batch importation
                    file_to_convert = {
                        'in_dir': dicom_path,
                        'out_dir': target_path,
                        'filename': os.path.splitext(target_filename)[0]
                    }
                    is_file_to_import = os.path.join(
                        os.getcwd(), target_path,
                        target_filename + ".nii" + gz_ext)
                    logger.debug('is_file_to_import=%s', is_file_to_import)
                    if os.path.isfile(is_file_to_import):
                        list_already_imported.append(
                            f"already imported: {is_file_to_import}")
                    else:
                        infiles_dcm2nii.append(file_to_convert)

                    # Create the symlink in sourcedata
                    sourcedata_link = os.path.join(sourcedata_target_path,
                                                   file_to_convert['filename'])
                    try:
                        link_already_exists = os.path.samefile(sourcedata_link,
                                                               dicom_path)
                    except FileNotFoundError:
                        link_already_exists = False
                    if not link_already_exists:
                        try:
                            if os.path.islink(sourcedata_link):
                                os.unlink(sourcedata_link)
                            os.makedirs(sourcedata_target_path, exist_ok=True)
                            os.symlink(dicom_path, sourcedata_link,
                                       target_is_directory=True)
                        except OSError:
                            logger.error('could not create a sourcedata '
                                         'symlink %s -> %s',
                                         sourcedata_target_path, dicom_path)

                    # Add descriptor(s) into the json file
                    filename_json = os.path.join(
                        target_path,
                        os.path.splitext(target_filename)[0] + '.json'
                    )
                    entities, _, _ = bids.parse_bids_name(target_filename)
                    task = entities.get('task')
                    if task:
                        dict_descriptors.update(
                            {filename_json: {
                                'TaskName': task,
                            }})

                    if len(value) == 4:
                        dict_descriptors.update({filename_json: value[3]})

    # Importation and conversion of dicom files
    dcm2nii_batch = {
        'Options': {
            'isGz': not no_gz,
            'isFlipY': data_orientation != 'dicom',  # default is True
            'isVerbose': False,
            'isCreateBIDS': True,
            'isOnlySingleFile': False
        },
        'Files': infiles_dcm2nii,
    }

    dcm2nii_batch_file = os.path.join(exp_info_path, 'batch_dcm2nii.yaml')
    with open(dcm2nii_batch_file, 'w') as f:
        yaml.dump(dcm2nii_batch, f)

    report_lines = ["-" * 80]
    for i in list_already_imported:
        report_lines.append(i)
        download_report.write(i)
    if list_already_imported:
        report_lines.append("-" * 80)
    for i in list_imported:
        report_lines.append(i)
        download_report.write(i)
    report_lines.append("-" * 80)
    logger.info("Summary of importation:\n%s", "\n".join(report_lines))

    report_lines = []
    for i in list_warning:
        report_lines.append('- ' + i)
        download_report.write('\n  WARNING: ' + i)
    if report_lines:
        logger.warning("Warnings:\n%s\n%s\n%s",
                       "-" * 80, "\n".join(report_lines), "-" * 80)
    download_report.close()

    if list_warning:
        do_continue = yes_no(f'There are {len(list_warning)} warnings (see '
                             'above. Do you want to ignore them and continue?',
                             default='no', noninteractive=False)
        if not do_continue:
            logger.fatal('Aborting upon user request.')
            return 1

    if dry_run:
        logger.info("no importation, dry-run option is enabled")
    else:
        cmd = ("dcm2niibatch", dcm2nii_batch_file)
        ret = subprocess.call(cmd)
        if ret != 0:
            logger.error('dcm2niibatch returned an error, see above')

        for file_to_convert in infiles_dcm2nii:
            generated_files = glob.glob(os.path.join(
                file_to_convert['out_dir'],
                file_to_convert['filename'] + '*'))
            for filename in generated_files:
                if not filename.endswith('.json'):
                    postprocess.rename_file_with_postfixes(filename)

        # loop for checking if downloaded are ok and create the downloaded
        # files
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
            os.environ['PATH'] = (os.environ['FSLDIR']
                                  + os.pathsep + os.environ['PATH'])

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
                cmd = (f"bids-validator {shlex.quote(target_root_path)} "
                       f"| tee {shlex.quote(bids_validation_report)}")
                subprocess.call(cmd, shell=True)
                print(f'\n\nSee the summary of bids validator at '
                      f'{bids_validation_report}')
            else:
                validator = BIDSValidator()
                os.chdir(target_root_path)
                for file_to_test in Path('.').glob('./**/*'):
                    if file_to_test.is_file():
                        file_to_test = '/' + str(file_to_test)
                        print(f'\nTest the following name of file: '
                              f'{file_to_test} with BIDSValidator')
                        print(validator.is_bids(file_to_test))

    print('\n')


def main(argv=sys.argv):
    prog = os.path.basename(argv[0])
    if sys.version_info < (3, 6):
        sys.stderr.write(f'ERROR: {prog} needs Python 3.6 or later\n')
        return 1
    if argv is None:
        argv = sys.argv
    # Parse arguments from console
    parser = argparse.ArgumentParser(
        description='NeuroSpin to BIDS conversion'
    )
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
    parser.add_argument('--dicom-orientation', dest='data_orientation',
                        action='store_const', const='dicom', default='default',
                        help='Use the DICOM convention for internal data '
                        'orientation in the resulting NIfTI files. The '
                        'default is to reorient the images to a direct '
                        'referential by flipping the rows. This option is NOT '
                        'recommended, as it leads to non-standard NIfTI files '
                        'and problems with X-flipped diffusion vectors. '
                        'It is included for compatibility with existing '
                        'databases since it was the behaviour of '
                        'neurospin_to_bids from January 2020 to February '
                        '2022.')
    parser.add_argument('--dry-run', '-n', '-dry-run',
                        action='store_true',
                        help='Test without importation of data')
    parser.add_argument('--noninteractive', action='store_true',
                        help='Do not request interactive input from the '
                        'terminal')
    parser.add_argument('--autolist', action='store_true',
                        help='Try to use the experimental autolist feature')
    parser.add_argument('--debug', dest='logging_level', action='store_const',
                        const=logging.DEBUG, default=logging.INFO,
                        help='Enable debugging messages')

    # LOAD CONSOLE ARGUMENTS
    args = parser.parse_args(argv[1:])

    # Configure logging to a file + colorized logging on stderr
    report_dir = os.path.join(args.root_path, 'report')
    os.makedirs(report_dir, exist_ok=True)
    logging.basicConfig(
        level=min(args.logging_level, logging.INFO),
        filename=os.path.join(report_dir, 'neurospin_to_bids.log'),
        filemode='a',
    )
    root_logger = logging.getLogger()
    formatter = logging.Formatter(f'{prog}: %(levelname)s: %(message)s')
    from logutils.colorize import ColorizingStreamHandler
    handler = ColorizingStreamHandler(sys.stderr)
    handler.setFormatter(formatter)
    handler.setLevel(args.logging_level)
    root_logger.addHandler(handler)
    logging.captureWarnings(True)

    logger.info('Started %s', ' '.join(shlex.quote(arg) for arg in argv))

    utils.set_noninteractive(args.noninteractive)
    acquisition_db.set_root_path(args.acquisition_dir)

    try:
        if args.autolist:
            from . import autolist
            autolist.autolist_dicom(os.path.join(args.root_path, 'exp_info'))
            return
        deface = yes_no('\nDo you want deface T1?', default=None,
                        noninteractive=False)
        return bids_acquisition_download(
            data_root_path=args.root_path,
            dataset_name=args.dataset_name,
            force_download=False,
            behav_path='exp_info/recorded_events',
            copy_events=args.copy_events,
            deface=deface,
            no_gz=args.no_gz,
            data_orientation=args.data_orientation,
            dry_run=args.dry_run,
        ) or 0
    except UserError as exc:
        logger.fatal(f'aborting due to user error: {exc}')
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
