# -*- coding: utf-8 -*-

import shutil

import neurospin_to_bids.__main__


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
