"""Read authenticated publication diagnostics; export bounded exception metadata privately."""
import json,os,re,sys,hashlib
from pathlib import Path
sys.path.insert(0,'experiments/ensemble_validation')
from private_reports import Api,SOURCE,DEST
source=Api(os.environ['GITHUB_TOKEN'])
run=source.call(SOURCE+'/actions/runs/43960512102')
if (run['head_sha'],run['path'],run['conclusion'])!=('055e438324a31e91754ddaa9b137624026590206','.github/workflows/ensemble-market-validation.yml','failure'):raise ValueError('Wrong source')
arts=source.call(SOURCE+'/actions/runs/43960512102/artifacts?per_page=100')['artifacts']
if not any(a['id']==14274449289 and a['name']=='private-logs-benchmark-43960512102' and a.get('digest')=='sha256:4506064ea9967d298acd9a9f65b6a5f4a00113f908441a569c9ad15f24677d5c' and not a['expired'] for a in arts):raise ValueError('Wrong diagnostic artifact')
exceptions=[]
for p in Path('diagnostic-input').rglob('*.log'):
 text=p.read_text(errors='replace')
 if 'Traceback (most recent call last):' not in text:continue
 trace=text[text.rfind('Traceback (most recent call last):'):]
 # Keep only Python frames and final exception lines, no data dumps or shell environment.
 lines=[l for l in trace.splitlines() if re.match(r'\s*File ".+", line \d+',l) or re.match(r'[A-Za-z_.]*(?:Error|Exception|StopIteration|AssertionError):?',l)]
 exceptions.append({'logSha256':hashlib.sha256(p.read_bytes()).hexdigest(),'exceptionFrames':lines[-25:]})
if not exceptions:raise ValueError('No exception diagnostic found')
v={'targetDate':'2026-11-17','sourceRunId':'43960512102','diagnosticArtifactId':14274449289,'exceptions':exceptions}
content=json.dumps(v,ensure_ascii=False,indent=2)+'\n'
if len(content.encode())>16000:raise ValueError('Diagnostic too large')
private=Api(os.environ['PRIVATE_REPORT_TOKEN'])
if private.call(DEST).get('private') is not True:raise ValueError('Private destination required')
head=private.call(DEST+'/git/ref/heads/main')['object']['sha'];tree=private.call(DEST+'/git/commits/'+head)['tree']['sha']
nt=private.call(DEST+'/git/trees','POST',{'base_tree':tree,'tree':[{'path':'deney/reports/2026-11-17/publication-failure.json','mode':'100644','type':'blob','content':content}]})['sha']
nc=private.call(DEST+'/git/commits','POST',{'message':'Record bounded primary publication diagnostic','parents':[head],'tree':nt})['sha']
private.call(DEST+'/git/refs/heads/main','PATCH',{'sha':nc,'force':False})
