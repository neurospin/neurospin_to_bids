# -*- coding: utf-8 -*-

import shutil
import subprocess
import sys


def test_app_help():
    exe = shutil.which('neurospin_to_bids')
    assert exe is not None
    print('Testing neurospin_to_bids executable: ' + exe)
    assert subprocess.call([sys.executable, exe, '-h']) == 0
    assert subprocess.call([sys.executable, exe, '--help']) == 0
