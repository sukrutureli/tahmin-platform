"""Apply privacy transport to production or experiment workflow without changing models."""
from pathlib import Path
import argparse
import copy
import re
import yaml

class Loader(yaml.SafeLoader):
    pass
Loader.yaml_implicit_resolvers = copy.deepcopy(Loader.yaml_implicit_resolvers)
for initial, values in Loader.yaml_implicit_resolvers.items():
    Loader.yaml_implicit_resolvers[initial] = [(tag, pattern) for tag, pattern in values
                                               if tag != 'tag:yaml.org,2002:bool']
Loader.add_implicit_resolver('tag:yaml.org,2002:bool', re.compile(r'^(?:true|false)$'), list('tf'))
class Dumper(yaml.SafeDumper):
    pass
def multiline(dumper, value):
    return dumper.represent_scalar('tag:yaml.org,2002:str', value, style='|' if '\n' in value else None)
Dumper.add_representer(str, multiline)

READ = '${{ secrets.FATHERTAHMIN_READ_TOKEN || secrets.ADMIN_USER }}'
WRITE = '${{ secrets.FATHERTAHMIN_WRITE_TOKEN || secrets.ADMIN_USER }}'
KEY = '${{ secrets.PRIVATE_ARTIFACT_KEY }}'


def prepare(text):
    data = yaml.load(text, Loader=Loader)
    for job_name, job in data['jobs'].items():
        steps = job['steps']
        if any(s.get('name') == 'Require private artifact key' for s in steps):
            raise ValueError('Workflow is already prepared')
        owns_checkout = any(s.get('uses', '').startswith('actions/checkout@')
                            and not s.get('with', {}).get('repository') for s in steps)
        if not owns_checkout:
            steps.insert(0, {'uses': 'actions/checkout@v4', 'with': {'persist-credentials': False}})
        for step in steps:
            use = step.get('uses', '')
            if use.startswith('actions/checkout@'):
                settings = step.setdefault('with', {})
                settings['persist-credentials'] = False
                if settings.get('repository') == 'sukrutureli/fathertahmin':
                    settings['token'] = READ
            if use.startswith('actions/upload-artifact@'):
                step['uses'] = './.github/actions/private-upload'
                settings = step['with']
                settings.pop('if-no-files-found', None)
                settings['key'] = KEY
            if use.startswith('actions/download-artifact@'):
                step['uses'] = './.github/actions/private-download'
                step['with'].update({'key': KEY, 'github-token': '${{ github.token }}'})
            if 'env' in step:
                if 'GITHUB_TOKEN' in step['env']:
                    step['env']['GITHUB_TOKEN'] = READ
                if step['env'].get('TOKEN') == '${{ secrets.ADMIN_USER }}':
                    step['env']['TOKEN'] = WRITE
            if 'run' in step:
                command = step['run']
                if 'PRIVATE_COMMAND' in command:
                    raise ValueError('Unexpected heredoc marker')
                step['run'] = ('python3 "$GITHUB_WORKSPACE/scripts/privacy/run_private.py" <<\'PRIVATE_COMMAND\'\n'
                               + command.rstrip() + '\nPRIVATE_COMMAND\n')
        # Fail closed before any scraper/application command can run.
        own_index = next(i for i, s in enumerate(steps) if s.get('uses', '').startswith('actions/checkout@')
                         and not s.get('with', {}).get('repository'))
        steps.insert(own_index + 1, {
            'name': 'Require private artifact key', 'env': {'PRIVATE_ARTIFACT_KEY': KEY},
            'run': 'python3 - <<\'PYKEY\'\nimport os, base64\ntry:\n k=base64.b64decode(os.environ.get("PRIVATE_ARTIFACT_KEY", ""),validate=True)\n assert len(k)==32\nexcept Exception:\n raise SystemExit("Configure PRIVATE_ARTIFACT_KEY before enabling this workflow")\nPYKEY\n'})
        # Encrypted logs stay available to the owner even when application commands fail.
        steps.append({'name': 'Prepare private diagnostic directory', 'if': 'always()',
                      'run': 'mkdir -p "$RUNNER_TEMP/tahmin-private-logs"'})
        steps.append({'name': 'Upload encrypted application diagnostics',
                      'if': 'always()',
                      'uses': './.github/actions/private-upload',
                      'with': {'name': 'private-logs-' + job_name + '-${{ github.run_id }}',
                               'path': '${{ runner.temp }}/tahmin-private-logs', 'key': KEY,
                               'retention-days': '7'}})
    # Standard read token for Java callers in every job; not used by checkout of own repo.
    data.setdefault('env', {})['GITHUB_TOKEN'] = READ
    return yaml.dump(data, Dumper=Dumper, sort_keys=False, allow_unicode=True, width=140)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('workflow', type=Path)
    args = parser.parse_args()
    args.workflow.write_text(prepare(args.workflow.read_text()))
