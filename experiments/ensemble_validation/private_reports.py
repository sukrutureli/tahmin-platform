"""Publish bounded experiment reports to one private repo; never publish datasets."""
import argparse,hashlib,json,os,re,urllib.request,urllib.error
from pathlib import Path

DEST='sukrutureli/fathertahmin'
SOURCE='sukrutureli/tahmin-platform'
PREFIX='deney/current/'
LIMIT=512*1024
TOTAL=3*1024*1024
JSON_FILES=['new-report-manifest.json','production-trigger.json','display-metadata.json','daily-evaluation.json','daily-journal.json','conditional-evaluation.json',
 'learned-daily-evaluation.json','mined-daily-evaluation.json','selection-evaluation.json',
 'selection-journal.json','match-choice-evaluation.json','match-choice-journal.json',
 'context-evaluation.json','stability-evaluation.json','stability-journal.json',
 'score-distribution-evaluation.json','input-manifest.json','reference-manifest.json',
 'error-diagnostics.json']
HTML_FILES=['futbol-yeni.html','basketbol-yeni.html','day-by-day.html','errors.html','context-comparison.html','stability.html',
 'models.html','selection.html','outcome-learning.html','best-matches.html']
SNAPSHOTS=['before-results-predictions.json','conditional-before-results.json',
 'learned-before-results.json','mined-before-results.json','selection-before-results.json',
 'match-choice-before-results.json','context-before-results.json','score-before-results.json',
 'stability-before-results.json']
OMIT={'eventIds','finishedEventIds'}

def compact(value):
    if isinstance(value,list):return [compact(x) for x in value]
    if not isinstance(value,dict):return value
    out={k:compact(v) for k,v in value.items() if k not in OMIT and k!='errors'}
    if isinstance(value.get('errors'),list):
        out['errorExampleCount']=len(value['errors'])
        out['errorExamples']=compact(value['errors'][:5])
    return out

def encoded(value):return json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n'
def digest(data):return hashlib.sha256(data).hexdigest()

def collect(root):
    root=Path(root);out={};source_hashes={}
    for name in JSON_FILES+HTML_FILES:
        path=root/name
        if not path.exists():continue
        if path.is_symlink() or not path.is_file():raise ValueError('Unsafe report source')
        raw=path.read_bytes();source_hashes[name]=digest(raw)
        data=encoded(compact(json.loads(raw))) if name.endswith('.json') else raw.decode('utf-8')
        if len(data.encode())>LIMIT:raise ValueError('Report size limit exceeded: '+name)
        out[name]=data
    for required in ['daily-evaluation.json','input-manifest.json','context-evaluation.json','stability-journal.json']:
        if required not in out:raise ValueError('Required report missing: '+required)
    snapshots=[]
    for name in SNAPSHOTS:
        p=root/name
        if p.exists():
            if p.is_symlink():raise ValueError('Unsafe snapshot')
            raw=p.read_bytes();v=json.loads(raw)
            snapshots.append({'file':name,'sha256':digest(raw),**{k:v[k] for k in ['date','targetDate','createdAt','selectionCreatedAt','ruleLearnedOn','modelSha256','version'] if k in v}})
    out['snapshot-index.json']=encoded(snapshots)
    history=root/'live-history.json'
    if history.exists():
        h=json.loads(history.read_text());coverage={}
        for sport in ['football','basketball']:
            rows=[r for r in h.get('fixtures',[]) if r.get('sport')==sport]
            coverage[sport]={'attemptedFixtures':len(rows),'bothSidesWithRows':sum(len(r.get('sides',[]))==2 and all(s.get('rows') for s in r['sides']) for r in rows)}
        out['history-coverage.json']=encoded({k:h.get(k) for k in ['targetDate','startedAt','completedAt','rateLimited','stoppedEarly','secondsPerSport']}|{'requestCount':len(h.get('requests',[])),'errorCount':len(h.get('errors',[])),'coverage':coverage})
    if sum(len(x.encode()) for x in out.values())>TOTAL:raise ValueError('Report package limit exceeded')
    return out,source_hashes

class Api:
    def __init__(self,token):
        if not token:raise ValueError('Missing report access token')
        self.token=token
    def call(self,path,method='GET',body=None):
        request=urllib.request.Request('https://api.github.com/repos/'+path,data=encoded(body).encode() if body is not None else None,method=method,headers={'Authorization':'Bearer '+self.token,'Accept':'application/vnd.github+json','User-Agent':'tahmin-private-reports','Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(request,timeout=45) as response:
                data=response.read();return json.loads(data) if data else None
        except urllib.error.HTTPError as e:
            raise RuntimeError('GitHub request failed with HTTP '+str(e.code)) from None

def publish(api,files,manifest):
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',manifest['targetDate']):raise ValueError('Invalid private report date')
    # Check immediately before every mutation attempt, not only at setup time.
    for attempt in range(3):
        if api.call(DEST).get('private') is not True:raise ValueError('Destination must be private')
        head=api.call(DEST+'/git/ref/heads/main')['object']['sha']
        tree=api.call(DEST+'/git/commits/'+head)['tree']['sha']
        entries=api.call(DEST+'/git/trees/'+tree+'?recursive=1')
        if entries.get('truncated'):raise ValueError('Incomplete destination tree')
        owned=set(JSON_FILES+HTML_FILES+['snapshot-index.json','history-coverage.json','checkpoint-manifest.json'])
        paths={x['path']:x for x in entries['tree'] if x['path'].startswith(PREFIX)}
        files=dict(files);files['checkpoint-manifest.json']=encoded(manifest)
        dated={name:files[name] for name in ['futbol-yeni.html','basketbol-yeni.html','new-report-manifest.json','checkpoint-manifest.json','stability-evaluation.json','context-evaluation.json','daily-evaluation.json'] if name in files}
        # Git blob hashes make identical reruns a no-op.
        def blob(text):
            b=text.encode();return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
        updates=[{'path':PREFIX+n,'mode':'100644','type':'blob','content':s} for n,s in files.items() if paths.get(PREFIX+n,{}).get('sha')!=blob(s)]
        updates += [{'path':'deney/reports/'+manifest['targetDate']+'/'+n,'mode':'100644','type':'blob','content':v} for n,v in dated.items() if not any(x['path']=='deney/reports/'+manifest['targetDate']+'/'+n and x['sha']==blob(v) for x in entries['tree'])]
        updates += [{'path':p,'mode':'100644','type':'blob','sha':None} for p in paths if p[len(PREFIX):] in owned and p[len(PREFIX):] not in files]
        if not updates:return False
        newtree=api.call(DEST+'/git/trees','POST',{'base_tree':tree,'tree':updates})['sha']
        commit=api.call(DEST+'/git/commits','POST',{'message':'Update private experiment reports '+manifest['targetDate']+' (source '+str(manifest['sourceRunId'])+')','tree':newtree,'parents':[head]})['sha']
        try:
            api.call(DEST+'/git/refs/heads/main','PATCH',{'sha':commit,'force':False});return True
        except RuntimeError:
            if attempt==2:raise
    raise RuntimeError('Private report update failed')

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--source-run',required=True);p.add_argument('--target-date',required=True);a=p.parse_args()
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',a.target_date) or not a.source_run.isdigit():raise ValueError('Invalid source')
    files,hashes=collect(a.root)
    if json.loads(files['daily-evaluation.json'])['date']!=a.target_date:raise ValueError('Report date mismatch')
    source=Api(os.environ.get('REPORT_SOURCE_TOKEN'));run=source.call(SOURCE+'/actions/runs/'+a.source_run)
    own=a.source_run==os.environ.get('GITHUB_RUN_ID')
    if run['head_branch']!='experiment/ensemble-market-validation' or (run.get('conclusion')!='success' and not (own and run['status']=='in_progress')):raise ValueError('Unverified experiment source run')
    artifacts=source.call(SOURCE+'/actions/runs/'+a.source_run+'/artifacts?per_page=100')['artifacts']
    name='ensemble-market-validation-'+a.target_date
    artifact=next((x for x in artifacts if x['name']==name and not x['expired']),None)
    if not artifact:raise ValueError('Encrypted source artifact missing')
    manifest={'targetDate':a.target_date,'sourceRunId':a.source_run,'sourceSha':run['head_sha'],'sourceArtifact':name,'sourceArtifactId':artifact['id'],'artifactUrl':f'https://github.com/{SOURCE}/actions/runs/{a.source_run}/artifacts/{artifact["id"]}',
      'policy':'Private report copies only. Event ID membership lists omitted; five error examples per block. Full datasets, snapshots, raw HTTP, and logs remain encrypted. Predictions and models unchanged.',
      'sourceFileSha256':hashes,'reports':{n:{'bytes':len(s.encode()),'sha256':digest(s.encode())} for n,s in files.items()}}
    changed=publish(Api(os.environ.get('PRIVATE_REPORT_TOKEN')),files,manifest)
    print('Private experiment report checkpoint '+('updated' if changed else 'unchanged')+'; '+str(len(files))+' bounded reports')

if __name__=='__main__':main()
