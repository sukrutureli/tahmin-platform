"""Run stdin as bash without leaking application output into public Actions logs."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path(os.environ.get('RUNNER_TEMP', tempfile.gettempdir())) / 'tahmin-private-logs'
root.mkdir(mode=0o700, parents=True, exist_ok=True)
fd, path = tempfile.mkstemp(prefix='step-', suffix='.log', dir=root)
with os.fdopen(fd, 'wb') as output:
    completed = subprocess.run(['bash', '--noprofile', '--norc', '-eo', 'pipefail'],
                               input=sys.stdin.buffer.read(), stdout=output, stderr=subprocess.STDOUT)
print('Private application step completed.' if completed.returncode == 0
      else 'Private application step failed. Details are in the encrypted diagnostic artifact.')
sys.exit(completed.returncode)
