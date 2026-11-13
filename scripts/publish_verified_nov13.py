"""One-time verified publication of the preserved Nov 13 recovery checkpoint."""
import json,os
from pathlib import Path
from private_reports import Api,SOURCE
from publish_primary import prepare,publish
RUN='43528252854'
ARTIFACT=14085134532
DIGEST='sha256:d072bb01e7b5a06a2f56de6dd6f6fcf1372b77afb8de2632a0f48bc2b31e81fd'
MODEL='35017ecf9f8992909e2f9090c8aff18c0e3c36d838312cb1202a3107c4cd61cb'
source=Api(os.environ['REPORT_SOURCE_TOKEN'])
run=source.call(SOURCE+'/actions/runs/'+RUN)
if (run['head_sha'],run['path'],run['head_branch'],run['conclusion'])!=('0239f0b4fdb0898f1e1a268765a834e15972c407','.github/workflows/recover-primary-2026-11-13.yml','experiment/ensemble-market-validation','success'):raise ValueError('Recovery origin mismatch')
art=next(a for a in source.call(SOURCE+'/actions/runs/'+RUN+'/artifacts?per_page=100')['artifacts'] if a['id']==ARTIFACT)
if art['name']!='primary-forecasts-2026-11-13' or art.get('digest')!=DIGEST or art.get('expired'):raise ValueError('Recovery artifact mismatch')
files,manifest=prepare(Path('pipeline-output'),'2026-11-13')
if manifest['modelSha256']!=MODEL:raise ValueError('Frozen model changed')
publish(Api(os.environ['PRIVATE_REPORT_TOKEN']),files,manifest,RUN,ARTIFACT)
