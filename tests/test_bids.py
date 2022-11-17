import pytest

import neurospin_to_bids.bids


def test_parse_valid_partial_bids_names():
    parsed = neurospin_to_bids.bids.parse_bids_name('T1w')
    assert parsed[0] == {}
    assert parsed[1] == 'T1w'
    assert parsed[2] == ''
    parsed = neurospin_to_bids.bids.parse_bids_name('_T1w')
    assert parsed[0] == {}
    assert parsed[1] == 'T1w'
    assert parsed[2] == ''
    parsed = neurospin_to_bids.bids.parse_bids_name('T1w.nii')
    assert parsed[0] == {}
    assert parsed[1] == 'T1w'
    assert parsed[2] == '.nii'
    parsed = neurospin_to_bids.bids.parse_bids_name('T1w.nii.gz')
    assert parsed[0] == {}
    assert parsed[1] == 'T1w'
    assert parsed[2] == '.nii.gz'
    parsed = neurospin_to_bids.bids.parse_bids_name('sub-toto_T1w')
    assert parsed[0] == {'sub': 'toto'}
    assert parsed[1] == 'T1w'
    assert parsed[2] == ''
    parsed = neurospin_to_bids.bids.parse_bids_name('sub-toto_ses-01_T1w')
    assert parsed[0] == {'sub': 'toto', 'ses': '01'}
    assert parsed[1] == 'T1w'
    assert parsed[2] == ''
    parsed = neurospin_to_bids.bids.parse_bids_name('sub-toto')
    assert parsed[0] == {'sub': 'toto'}
    assert parsed[1] == ''
    assert parsed[2] == ''
    parsed = neurospin_to_bids.bids.parse_bids_name('sub-toto')
    assert parsed[0] == {'sub': 'toto'}
    assert parsed[1] == ''
    assert parsed[2] == ''
    parsed = neurospin_to_bids.bids.parse_bids_name('.json')
    assert parsed[0] == {}
    assert parsed[1] == ''
    assert parsed[2] == '.json'
    parsed = neurospin_to_bids.bids.parse_bids_name('sub-toto_ses-abcd_')
    assert parsed[0] == {'sub': 'toto', 'ses': 'abcd'}
    assert parsed[1] == ''
    assert parsed[2] == ''


def test_parse_edgecase_partial_bids_names():
    parsed = neurospin_to_bids.bids.parse_bids_name('')
    assert parsed[0] == {}
    assert parsed[1] == ''
    assert parsed[2] == ''
    parsed = neurospin_to_bids.bids.parse_bids_name('sub-aé-o_bold.tutu')
    assert parsed[0] == {'sub': 'aé-o'}
    assert parsed[1] == 'bold'
    assert parsed[2] == '.tutu'
    parsed = neurospin_to_bids.bids.parse_bids_name('_sub-a')
    assert parsed[0] == {'sub': 'a'}
    assert parsed[1] == ''
    assert parsed[2] == ''
    parsed = neurospin_to_bids.bids.parse_bids_name('sub-a_')
    assert parsed[0] == {'sub': 'a'}
    assert parsed[1] == ''
    assert parsed[2] == ''
    parsed = neurospin_to_bids.bids.parse_bids_name('sub-_ses-')
    assert parsed[0] == {'sub': '', 'ses': ''}
    assert parsed[1] == ''
    assert parsed[2] == ''
    parsed = neurospin_to_bids.bids.parse_bids_name('sub-a_b_ses-c')
    assert parsed[0] == {'sub': 'a_b', 'ses': 'c'}
    assert parsed[1] == ''
    assert parsed[2] == ''
    parsed = neurospin_to_bids.bids.parse_bids_name('sub-a_ses-__')
    assert parsed[0] == {'sub': 'a', 'ses': '_'}
    assert parsed[1] == ''
    assert parsed[2] == ''


def test_parse_invalid_partial_bids_names():
    with pytest.raises(neurospin_to_bids.bids.BIDSError):
        neurospin_to_bids.bids.parse_bids_name('-sub-a_bold')


def test_validate_bids_names():
    with pytest.warns(neurospin_to_bids.bids.BIDSWarning):
        neurospin_to_bids.bids.validate_bids_partial_name('sub-a_b_T1w.nii')
    with pytest.warns(neurospin_to_bids.bids.BIDSWarning):
        neurospin_to_bids.bids.validate_bids_partial_name('sub-a__bold')
    with pytest.warns(neurospin_to_bids.bids.BIDSWarning):
        neurospin_to_bids.bids.validate_bids_partial_name('sub-a-b_bold.nii')
    with pytest.warns(neurospin_to_bids.bids.BIDSWarning):
        neurospin_to_bids.bids.validate_bids_partial_name('sub-a.b_bold.nii')
