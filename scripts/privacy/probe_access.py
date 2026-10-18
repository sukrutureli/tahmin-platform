"""Probe configured repo access without publishing files or exposing credentials."""
import base64
import json
import os
from pathlib import Path
import subprocess
import tempfile
from urllib.request import Request, urlopen


stage = "key validation"

def main():
    global stage
    key = base64.b64decode(os.environ.get('PRIVATE_ARTIFACT_KEY', ''), validate=True)
    if len(key) != 32:
        raise ValueError('Configure a valid PRIVATE_ARTIFACT_KEY')
    print('Artifact key format accepted.')
    stage = 'write token presence'
    token = os.environ.get('FATHERTAHMIN_WRITE_TOKEN', '')
    if not token:
        raise ValueError('Configure FATHERTAHMIN_WRITE_TOKEN')
    headers = {'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json',
               'User-Agent': 'tahmin-private-readiness'}
    stage = 'GitHub Contents API read'
    for path in ('futbol/futbol.html', 'basketbol/basketbol.html'):
        request = Request('https://api.github.com/repos/sukrutureli/fathertahmin/contents/' + path + '?ref=main', headers=headers)
        with urlopen(request, timeout=30) as response:
            if response.status != 200:
                raise ValueError('Source report not readable')
            # Consume metadata locally; never print response body or data.
            response.read()
    print('Both source reports readable.')
    stage = 'authenticated Git clone'
    with tempfile.TemporaryDirectory() as folder:
        env = dict(os.environ)
        env.update({'GIT_TERMINAL_PROMPT': '0', 'GIT_CONFIG_COUNT': '1',
                    'GIT_CONFIG_KEY_0': 'http.https://github.com/.extraheader',
                    'GIT_CONFIG_VALUE_0': 'Authorization: Basic ' + base64.b64encode(('x-access-token:' + token).encode()).decode()})
        commands = [
            ['git', 'clone', '--quiet', '--filter=blob:none', '--no-checkout', '--depth=1',
             'https://github.com/sukrutureli/fathertahmin.git', folder + '/repo'],
            ['git', '-C', folder + '/repo', 'push', '--dry-run', '--quiet', 'origin', 'HEAD:refs/heads/main']]
        for index, command in enumerate(commands):
            stage = 'authenticated Git clone' if index == 0 else 'Git push dry-run'
            result = subprocess.run(command, env=env, capture_output=True, timeout=120)
            if result.returncode:
                message = result.stderr.decode('utf-8', errors='replace')
                import re
                safe = message.replace(token, '***').replace(env['GIT_CONFIG_VALUE_0'].split('Basic ',1)[1], '***')
                safe = re.sub(r'(https?://)[^/\s]*@', r'\1[redacted]@', safe)
                print('Sanitized git diagnostic: ' + safe[-1500:])
                if '403' in message or 'Permission' in message or 'denied' in message:
                    print('GitHub rejected the write handshake: check Contents read/write on the selected repository.')
                elif 'workflow' in message.lower():
                    print('GitHub reported a workflow-permission restriction during the dry-run.')
                elif 'rejected' in message.lower() or 'fetch first' in message.lower():
                    print('Remote head changed or push policy rejected this dry-run.')
                else:
                    print('Git transport failed before a write handshake could be verified.')
                raise ValueError('Repository access/push handshake failed')
    print('Configured key accepted; both reports readable; git push dry-run accepted. No repository data changed.')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        raise SystemExit('Private readiness probe failed at: ' + stage + '. No secret values are printed.') from None
