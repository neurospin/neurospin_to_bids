import distutils.spawn
import subprocess

def test_app_help():
    exe = distutils.spawn.find_executable('neurospin_to_bids')
    assert exe is not None
    print('Testing neurospin_to_bids executable: ' + exe)
    assert subprocess.call([exe, '-h']) == 0
    assert subprocess.call([exe, '--help']) == 0
