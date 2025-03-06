import collections.abc
import logging
import shutil

import yaml

import neurospin_to_bids.__main__


def test_simple_import_mri(tmp_path, caplog):
    ses_dir = (
        tmp_path / 'acq' / 'database' / 'Prisma_fit' / '20000101' / 'aa000001-001_001'
    )
    (ses_dir / '000003_mprage-sag-T1').mkdir(parents=True)
    (ses_dir / '000004_mbepi-3mm-PA').mkdir()
    exp_info_dir = tmp_path / 'exp_info'
    exp_info_dir.mkdir()
    with (exp_info_dir / 'participants_to_import.tsv').open(mode='w') as f:
        f.write(
            'participant_id\tNIP\tacq_date\tlocation\tto_import\n'
            'sub-01\taa000001\t2000-01-01\tprisma\t'
            '[[3,"anat","T1w"],[4,"func","task-rest_bold"]]\n'
        )

    exe = shutil.which('neurospin_to_bids')
    assert exe is not None
    ret = neurospin_to_bids.__main__.main(
        [
            'neurospin_to_bids',
            '--noninteractive',
            '--dry-run',
            '--acquisition-dir',
            str(tmp_path / 'acq'),
            '--root-path',
            str(tmp_path),
        ]
    )
    assert ret == 0
    for record in caplog.records:
        assert record.levelno < logging.ERROR

    with (exp_info_dir / 'batch_dcm2nii.yaml').open() as f:
        batch = yaml.safe_load(f)
    assert isinstance(batch, collections.abc.Mapping)
    assert 'Options' in batch
    assert batch['Options'].get('isFlipY', True) is True
    assert batch['Options'].get('isGenerateBids', True) is True
    assert batch['Options'].get('isGz', False) is True
    assert 'Files' in batch
    assert batch['Files'] == [
        {
            'filename': 'sub-01_T1w',
            'in_dir': str(ses_dir / '000003_mprage-sag-T1'),
            'out_dir': str(tmp_path / 'rawdata' / 'sub-01' / 'anat'),
        },
        {
            'filename': 'sub-01_task-rest_bold',
            'in_dir': str(ses_dir / '000004_mbepi-3mm-PA'),
            'out_dir': str(tmp_path / 'rawdata' / 'sub-01' / 'func'),
        },
    ]


def test_import_mri_with_unquoted_infos_participant(tmp_path, caplog):
    ses_dir = (
        tmp_path / 'acq' / 'database' / 'Prisma_fit' / '20000101' / 'aa000001-001_001'
    )
    (ses_dir / '000003_mprage-sag-T1').mkdir(parents=True)
    exp_info_dir = tmp_path / 'exp_info'
    exp_info_dir.mkdir()
    with (exp_info_dir / 'participants_to_import.tsv').open(mode='w') as f:
        f.write(
            'participant_id\tNIP\tinfos_participant\t'
            'acq_date\tlocation\tto_import\n'
            'sub-01\taa000001\t{"age": 20, "sex": "F"}\t'
            '2000-01-01\tprisma\t[[3,"anat","T1w"]]\n'
        )

    exe = shutil.which('neurospin_to_bids')
    assert exe is not None
    ret = neurospin_to_bids.__main__.main(
        [
            'neurospin_to_bids',
            '--noninteractive',
            '--dry-run',
            '--acquisition-dir',
            str(tmp_path / 'acq'),
            '--root-path',
            str(tmp_path),
        ]
    )
    assert ret == 0
    for record in caplog.records:
        assert record.levelno < logging.ERROR


def test_import_already_imported_data(tmp_path, caplog):
    ses_dir = (
        tmp_path / 'acq' / 'database' / 'Prisma_fit' / '20000101' / 'aa000001-001_001'
    )
    (ses_dir / '000003_mprage-sag-T1').mkdir(parents=True)
    exp_info_dir = tmp_path / 'exp_info'
    exp_info_dir.mkdir()
    already_imported_anat_dir = tmp_path / 'rawdata' / 'sub-01' / 'anat'
    already_imported_t1w_nii = already_imported_anat_dir / 'sub-01_T1w.nii.gz'
    already_imported_t1w_json = already_imported_anat_dir / 'sub-01_T1w.json'
    already_imported_anat_dir.mkdir(parents=True)
    already_imported_t1w_nii.touch()
    already_imported_t1w_json.touch()
    with (exp_info_dir / 'participants_to_import.tsv').open(mode='w') as f:
        f.write(
            'participant_id\tNIP\tinfos_participant\t'
            'acq_date\tlocation\tto_import\n'
            'sub-01\taa000001\t{"age": 20, "sex": "F"}\t'
            '2000-01-01\tprisma\t[[3,"anat","T1w"]]\n'
        )

    exe = shutil.which('neurospin_to_bids')
    assert exe is not None
    caplog.set_level(logging.INFO)
    ret = neurospin_to_bids.__main__.main(
        [
            'neurospin_to_bids',
            '--noninteractive',
            '--dry-run',
            '--acquisition-dir',
            str(tmp_path / 'acq'),
            '--root-path',
            str(tmp_path),
        ]
    )
    assert ret == 0
    for record in caplog.records:
        assert record.levelno < logging.ERROR
    assert any('already imported:' in record.message for record in caplog.records)


def test_import_mri_with_quoted_infos_participant(tmp_path, caplog):
    ses_dir = (
        tmp_path / 'acq' / 'database' / 'Prisma_fit' / '20000101' / 'aa000001-001_001'
    )
    (ses_dir / '000003_mprage-sag-T1').mkdir(parents=True)
    exp_info_dir = tmp_path / 'exp_info'
    exp_info_dir.mkdir()
    with (exp_info_dir / 'participants_to_import.tsv').open(mode='w') as f:
        f.write(
            'participant_id\tNIP\tinfos_participant\t'
            'acq_date\tlocation\tto_import\n'
            'sub-01\taa000001\t"{""age"": 20, ""sex"": ""F""}"\t'
            '2000-01-01\tprisma\t[[3,"anat","T1w"]]\n'
        )

    exe = shutil.which('neurospin_to_bids')
    assert exe is not None
    ret = neurospin_to_bids.__main__.main(
        [
            'neurospin_to_bids',
            '--noninteractive',
            '--dry-run',
            '--acquisition-dir',
            str(tmp_path / 'acq'),
            '--root-path',
            str(tmp_path),
        ]
    )
    assert ret == 0
    for record in caplog.records:
        assert record.levelno < logging.ERROR


def test_import_mri_with_empty_json_fields(tmp_path, caplog):
    ses_dir = (
        tmp_path / 'acq' / 'database' / 'Prisma_fit' / '20000101' / 'aa000001-001_001'
    )
    (ses_dir / '000003_mprage-sag-T1').mkdir(parents=True)
    exp_info_dir = tmp_path / 'exp_info'
    exp_info_dir.mkdir()
    with (exp_info_dir / 'participants_to_import.tsv').open(mode='w') as f:
        f.write(
            'participant_id\tNIP\tinfos_participant\t'
            'acq_date\tlocation\tto_import\n'
            'sub-01\taa000001\t   \t'
            '2000-01-01\tprisma\t   \n'
        )

    exe = shutil.which('neurospin_to_bids')
    assert exe is not None
    ret = neurospin_to_bids.__main__.main(
        [
            'neurospin_to_bids',
            '--noninteractive',
            '--dry-run',
            '--acquisition-dir',
            str(tmp_path / 'acq'),
            '--root-path',
            str(tmp_path),
        ]
    )
    assert ret == 0
    for record in caplog.records:
        assert record.levelno < logging.ERROR


def test_simple_import_mri_invalid_sequence(tmp_path):
    ses_dir = (
        tmp_path / 'acq' / 'database' / 'Prisma_fit' / '20000101' / 'aa000001-001_001'
    )
    ses_dir.mkdir(parents=True)
    exp_info_dir = tmp_path / 'exp_info'
    exp_info_dir.mkdir()
    with (exp_info_dir / 'participants_to_import.tsv').open(mode='w') as f:
        f.write(
            'participant_id\tNIP\tacq_date\tlocation\tto_import\n'
            'sub-01\taa000001\t2000-01-01\tprisma\t'
            '[[3,"anat","T1w"]]\n'
        )

    exe = shutil.which('neurospin_to_bids')
    assert exe is not None
    ret = neurospin_to_bids.__main__.main(
        [
            'neurospin_to_bids',
            '--noninteractive',
            '--dry-run',
            '--acquisition-dir',
            str(tmp_path / 'acq'),
            '--root-path',
            str(tmp_path),
        ]
    )
    assert ret == 1
