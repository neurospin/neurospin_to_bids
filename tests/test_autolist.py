# -*- coding: utf-8 -*-

import datetime
import json

import neurospin_to_bids.acquisition_db
import neurospin_to_bids.autolist
import neurospin_to_bids.exp_info


def test_autolist_mri(tmp_path, monkeypatch):
    ses_dir = (tmp_path / 'acq' / 'database' / 'Prisma_fit' / '20000101'
               / 'aa000001-0001_001')
    (ses_dir / '000003_mprage-sag-T1').mkdir(parents=True)
    (ses_dir / '000004_mbepi-3mm-PA').mkdir()
    (ses_dir / '000008_b0-gre-field-mapping').mkdir()
    (ses_dir / '000009_b0-gre-field-mapping').mkdir()
    (ses_dir / '000012_mbepi-3mm-PA').mkdir()
    (ses_dir / '000014_interleaved').mkdir()
    (ses_dir / '000015_interleaved').mkdir()
    (ses_dir / '000016_interleaved').mkdir()
    decoy_ses_dir = (tmp_path / 'acq' / 'database' / 'Prisma_fit' / '20000101'
                     / 'aa000001-0001_002')
    decoy_ses_dir.mkdir()
    exp_info_dir = tmp_path / 'exp_info'
    exp_info_dir.mkdir()
    with (exp_info_dir / 'participants_list.tsv').open(mode='w') as f:
        f.write('participant_id\tNIP\tacq_date\tlocation\n'
                'sub-01\taa000001\t2000-01-01\tprisma\n')
    with (exp_info_dir / 'autolist.yaml').open(mode='w') as f:
        json.dump({
            "rules": [
                {
                    "SeriesDescription": "mprage-sag-T1",
                    "data_type": "anat",
                    "bids_name": "T1w",
                },
                {
                    "SeriesDescription": "mbepi*",
                    "data_type": "func",
                    "bids_name": "task-rest_run-1_bold",
                    "metadata": {
                        "TaskName": "rest",
                    },
                },
                {
                    "SeriesDescription": "b0-gre-field-mapping",
                    "data_type": "fmap",
                    "consecutive_series": [
                        {
                            "bids_name": "magnitude1",
                        },
                        {
                            "bids_name": "phasediff",
                        },
                    ]
                },
                {
                    "SeriesDescription": "interleaved",
                    "data_type": "anat",
                    "bids_name": "T2w",
                    "repetitions": [
                        "acq-il1",
                        "acq-il2",
                    ],
                },
            ]
        }, f)

    monkeypatch.setattr(neurospin_to_bids.acquisition_db,
                        'ACQUISITION_ROOT_PATH',
                        str(tmp_path / 'acq'))
    neurospin_to_bids.autolist.autolist_dicom(str(exp_info_dir))

    with (exp_info_dir / 'participants_to_import.tsv').open() as f:
        print(f.read())

    generated_list = list(neurospin_to_bids.exp_info.iterate_participants_list(
        str(exp_info_dir / 'participants_to_import.tsv'), strict=True))
    assert len(generated_list) == 1
    assert generated_list[0] == {
        'subject_label': 'sub-01',
        'NIP': 'aa000001-0001_001',
        'infos_participant': {},
        'session_label': '',
        'acq_date': datetime.date(2000, 1, 1),
        'location': 'prisma',
        'to_import': [
            [3, 'anat', 'T1w'],
            [4, 'func', 'task-rest_run-1_bold', {'TaskName': 'rest'}],
            [8, 'fmap', 'magnitude1'],
            [9, 'fmap', 'phasediff'],
            [12, 'func', 'task-rest_run-2_bold', {'TaskName': 'rest'}],
            [14, 'anat', 'acq-il1_run-1_T2w'],
            [15, 'anat', 'acq-il2_T2w'],
            [16, 'anat', 'acq-il1_run-2_T2w'],
        ],
    }

    # exe = shutil.which('neurospin_to_bids')
    # assert exe is not None
    # ret = neurospin_to_bids.__main__.main([
    #     'neurospin_to_bids', '--noninteractive', '--dry-run',
    #     '--acquisition-dir', str(tmp_path / 'acq'),
    #     '--root-path', str(tmp_path)
    # ])
    # assert ret == 0
