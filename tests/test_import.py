import collections.abc
import shutil

import neurospin_to_bids.__main__

import yaml


def test_simple_import_mri(tmp_path):
    ses_dir = (tmp_path / 'acq' / 'database' / 'Prisma_fit' / '20000101'
               / 'aa000001-001_001')
    (ses_dir / '000003_mprage-sag-T1').mkdir(parents=True)
    (ses_dir / '000004_mbepi-3mm-PA').mkdir()
    exp_info_dir = tmp_path / 'exp_info'
    exp_info_dir.mkdir()
    with (exp_info_dir / 'participants_to_import.tsv').open(mode='w') as f:
        f.write('participant_id\tNIP\tacq_date\tlocation\tto_import\n'
                'sub-01\taa000001\t2000-01-01\tprisma\t'
                '[[3,"anat","T1w"],[4,"func","task-rest_bold"]]\n')

    exe = shutil.which('neurospin_to_bids')
    assert exe is not None
    ret = neurospin_to_bids.__main__.main([
        'neurospin_to_bids', '--noninteractive', '--dry-run',
        '--acquisition-dir', str(tmp_path / 'acq'),
        '--root-path', str(tmp_path)
    ])
    assert ret == 0

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


def test_import_mri_with_unquoted_infos_participant(tmp_path):
    ses_dir = (tmp_path / 'acq' / 'database' / 'Prisma_fit' / '20000101'
               / 'aa000001-001_001')
    (ses_dir / '000003_mprage-sag-T1').mkdir(parents=True)
    exp_info_dir = tmp_path / 'exp_info'
    exp_info_dir.mkdir()
    with (exp_info_dir / 'participants_to_import.tsv').open(mode='w') as f:
        f.write('participant_id\tNIP\tinfos_participant\t'
                'acq_date\tlocation\tto_import\n'
                'sub-01\taa000001\t{"age": 20, "sex": "F"}\t'
                '2000-01-01\tprisma\t[[3,"anat","T1w"]]\n')

    exe = shutil.which('neurospin_to_bids')
    assert exe is not None
    ret = neurospin_to_bids.__main__.main([
        'neurospin_to_bids', '--noninteractive', '--dry-run',
        '--acquisition-dir', str(tmp_path / 'acq'),
        '--root-path', str(tmp_path)
    ])
    assert ret == 0


def test_import_mri_with_quoted_infos_participant(tmp_path):
    ses_dir = (tmp_path / 'acq' / 'database' / 'Prisma_fit' / '20000101'
               / 'aa000001-001_001')
    (ses_dir / '000003_mprage-sag-T1').mkdir(parents=True)
    exp_info_dir = tmp_path / 'exp_info'
    exp_info_dir.mkdir()
    with (exp_info_dir / 'participants_to_import.tsv').open(mode='w') as f:
        f.write('participant_id\tNIP\tinfos_participant\t'
                'acq_date\tlocation\tto_import\n'
                'sub-01\taa000001\t"{""age"": 20, ""sex"": ""F""}"\t'
                '2000-01-01\tprisma\t[[3,"anat","T1w"]]\n')

    exe = shutil.which('neurospin_to_bids')
    assert exe is not None
    ret = neurospin_to_bids.__main__.main([
        'neurospin_to_bids', '--noninteractive', '--dry-run',
        '--acquisition-dir', str(tmp_path / 'acq'),
        '--root-path', str(tmp_path)
    ])
    assert ret == 0


def test_simple_import_mri_invalid_sequence(tmp_path):
    ses_dir = (tmp_path / 'acq' / 'database' / 'Prisma_fit' / '20000101'
               / 'aa000001-001_001')
    ses_dir.mkdir(parents=True)
    exp_info_dir = tmp_path / 'exp_info'
    exp_info_dir.mkdir()
    with (exp_info_dir / 'participants_to_import.tsv').open(mode='w') as f:
        f.write('participant_id\tNIP\tacq_date\tlocation\tto_import\n'
                'sub-01\taa000001\t2000-01-01\tprisma\t'
                '[[3,"anat","T1w"]]\n')

    exe = shutil.which('neurospin_to_bids')
    assert exe is not None
    ret = neurospin_to_bids.__main__.main([
        'neurospin_to_bids', '--noninteractive', '--dry-run',
        '--acquisition-dir', str(tmp_path / 'acq'),
        '--root-path', str(tmp_path)
    ])
    assert ret == 1
