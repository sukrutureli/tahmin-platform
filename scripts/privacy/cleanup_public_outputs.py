"""Backup-first cleanup of old Actions outputs. No source deletion before remote backup verification."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

import artifact

CUTOFF = '2026-10-18T00:43:00Z'
PROTECTED = {39084004424, 39084079657}
MAX_SOURCE = 2 * 1024**3

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None

class Api:
    def __init__(self):
        self.repo = os.environ['GITHUB_REPOSITORY']
        if self.repo != 'sukrutureli/tahmin-platform':
            raise ValueError('Unexpected repository')
        self.token = os.environ['GH_TOKEN']
        self.legacy = os.environ.get('LEGACY_TOKEN', '')
        self.disabled_legacy = set()
        self.reported = set()
        self.opener = urllib.request.build_opener(NoRedirect())
    def request(self, path, method='GET', missing_ok=False):
        for attempt in range(6):
            primary=self.legacy if self.legacy and method not in self.disabled_legacy else self.token
            tokens=list(dict.fromkeys([primary,self.token]))
            delays=[];permission_failed=False
            for token in tokens:
                req=urllib.request.Request('https://api.github.com/repos/'+self.repo+'/'+path,
                    headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json',
                             'User-Agent':'private-output-cleanup','X-GitHub-Api-Version':'2022-11-28'},method=method)
                try:
                    response=self.opener.open(req,timeout=120)
                    if permission_failed and token==self.token:self.disabled_legacy.add(method)
                    if method not in self.reported:
                        print('API_ACCESS='+method+' '+('stored-token' if token==self.legacy else 'workflow-token')+
                              ' remaining='+response.headers.get('X-RateLimit-Remaining','unknown'))
                        self.reported.add(method)
                    return response
                except urllib.error.HTTPError as error:
                    if error.code in (301,302,303,307,308):return error
                    exhausted=error.headers.get('X-RateLimit-Remaining')=='0'
                    if error.code==429 or (error.code==403 and exhausted):
                        delay=int(error.headers.get('Retry-After','30'))
                        if exhausted:delay=max(delay,int(error.headers.get('X-RateLimit-Reset','0'))-int(time.time())+2)
                        delays.append(max(1,min(delay,3700)));continue
                    if token!=tokens[-1] and error.code in (401,403,404):
                        permission_failed=True;continue
                    if missing_ok and error.code in (404,410):return None
                    raise RuntimeError('GitHub API operation failed with HTTP '+str(error.code)) from None
            if delays:
                print('GitHub API limit reached; waiting for reset without deleting unverified data.')
                time.sleep(min(delays));continue
        raise RuntimeError('GitHub rate limit persisted')
    def json(self,path,missing_ok=False):
        response=self.request(path,missing_ok=missing_ok)
        return None if response is None else json.load(response)
    def pages(self,path,key):
        result=[]
        for page in range(1,101):
            obj=self.json(path+('&' if '?' in path else '?')+'per_page=100&page='+str(page))
            values=obj[key];result.extend(values)
            if len(values)<100:return result
        raise RuntimeError('Inventory exceeds bounded pagination; refuse partial cleanup')
    def download(self,path,target):
        response=self.request(path,missing_ok=True)
        if response is None:return False
        if response.code in (301,302,303,307,308):
            location=response.headers.get('Location','');url=urllib.parse.urlparse(location)
            host=url.hostname or ''
            allowed=(host.endswith('.blob.core.windows.net') or host.endswith('.githubusercontent.com')
                     or host.endswith('.actions.githubusercontent.com') or host.endswith('.s3.amazonaws.com')
                     or host.endswith('.amazonaws.com') or host=='api.github.com')
            if url.scheme!='https' or not allowed or url.username or url.password:
                raise RuntimeError('Archive redirect is not an approved HTTPS storage host')
            # Explicitly omit GitHub Authorization on signed storage redirects.
            response=urllib.request.urlopen(urllib.request.Request(location),timeout=120)
        total=0
        with open(target,'wb') as output:
            while True:
                chunk=response.read(1024*1024)
                if not chunk:break
                total+=len(chunk)
                if total>MAX_SOURCE:raise RuntimeError('Source archive exceeds bounded backup size')
                output.write(chunk)
        if not zipfile.is_zipfile(target):raise RuntimeError('Source response was not a ZIP archive')
        return True

def eligible(item):
    run=int(item.get('workflow_run',{}).get('id') or item.get('id',0))
    return item.get('created_at','9999') < CUTOFF and run not in PROTECTED

def make_batches(items, maximum=20, byte_limit=800*1024**2):
    batches=[];current=[];size=0
    for item in items:
        estimate=item.get('size',10*1024**2)
        if current and (len(current)>=maximum or size+estimate>byte_limit):
            batches.append(current);current=[];size=0
        current.append(item);size+=estimate
    if current:batches.append(current)
    if len(batches)>256:raise RuntimeError('Plan exceeds GitHub matrix limit')
    return [{'batch':i,'items':items} for i,items in enumerate(batches)]

def inventory(api):
    artifacts=api.pages('actions/artifacts','artifacts')
    runs=api.pages('actions/runs?status=completed&created='+urllib.parse.quote('<'+CUTOFF),'workflow_runs')
    items=[]
    for a in artifacts:
        if eligible(a) and not a.get('expired') and not a['name'].startswith('private-backup-'):
            items.append({'kind':'artifact','id':int(a['id']),'run':int(a.get('workflow_run',{}).get('id',0)),
                          'name':a['name'],'created':a['created_at'],'size':int(a['size_in_bytes'])})
    for r in runs:
        if eligible(r):
            probe=api.request(f"actions/runs/{r['id']}/logs",missing_ok=True)
            if probe is not None:
                probe.close()
                items.append({'kind':'logs','id':int(r['id']),'name':r.get('name',''),
                              'created':r['created_at'],'size':10*1024**2})
    # Stable order ensures reruns only see remaining source objects.
    return sorted(items,key=lambda x:(x['kind'],x['id']))

def source_path(item):
    if item['kind']=='artifact':return f"actions/artifacts/{item['id']}/zip"
    if item['kind']=='logs':return f"actions/runs/{item['id']}/logs"
    raise ValueError('Unknown source kind')

def validate_item(item):
    if item.get('kind') not in ('artifact','logs') or not isinstance(item.get('id'),int):
        raise ValueError('Invalid cleanup item')
    if item.get('created','9999')>=CUTOFF or item['id'] in PROTECTED or item.get('run') in PROTECTED:
        raise ValueError('Refuse protected or post-cutover output')

def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as source:
        for chunk in iter(lambda:source.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def backup(api,items,root):
    artifact.key()  # Validate before touching source storage.
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    proof=[]
    for item in items:
        validate_item(item)
        stem=item['kind']+'-'+str(item['id']);stage=root.parent/('stage-'+stem)
        stage.mkdir(parents=True,exist_ok=True)
        source=stage/'archive.zip'
        if not api.download(source_path(item),source):
            proof.append({'item':item,'already_absent':True});shutil.rmtree(stage);continue
        checksum=sha(source)
        (stage/'source.json').write_text(json.dumps({**item,'source_sha256':checksum},indent=2))
        encrypted=root/(stem+'.enc');artifact.pack(stage,encrypted)
        restored=root.parent/('verify-'+stem);artifact.unpack(encrypted,restored)
        if sha(restored/'archive.zip')!=checksum:raise RuntimeError('Backup roundtrip hash mismatch')
        proof.append({'item':item,'file':encrypted.name,'cipher_sha256':sha(encrypted)})
        shutil.rmtree(stage);shutil.rmtree(restored)
    (root/'proof.json').write_text(json.dumps(proof,indent=2))
    # proof contains IDs and archive metadata only; source payload and original ZIP are encrypted.
    print('BACKUP_VERIFIED='+str(sum(not p.get('already_absent') for p in proof)))


def delete_after_remote_verification(api,root,remote_id):
    root=Path(root);proof=json.loads((root/'proof.json').read_text())
    expected='private-backup-'+os.environ['GITHUB_RUN_ID']+'-'+os.environ['BATCH_NUMBER']
    remote=api.json('actions/artifacts/'+str(remote_id))
    if remote.get('name')!=expected or remote.get('expired') or int(remote.get('workflow_run',{}).get('id',0))!=int(os.environ['GITHUB_RUN_ID']):
        raise RuntimeError('Remote backup artifact is not the current verified bundle')
    # Download the published ZIP and compare every encrypted member before deleting originals.
    archive=root.parent/'remote-backup.zip'
    if not api.download('actions/artifacts/'+str(remote_id)+'/zip',archive):raise RuntimeError('Remote backup unavailable')
    with zipfile.ZipFile(archive) as z:
        for record in proof:
            if record.get('already_absent'):continue
            with z.open(record['file']) as source:
                h=hashlib.sha256()
                for chunk in iter(lambda:source.read(1024*1024),b''):h.update(chunk)
            if h.hexdigest()!=record['cipher_sha256']:raise RuntimeError('Remote encrypted backup hash mismatch')
    deleted=0
    for record in proof:
        item=record['item'];validate_item(item)
        if record.get('already_absent'):continue
        path=f"actions/artifacts/{item['id']}" if item['kind']=='artifact' else f"actions/runs/{item['id']}/logs"
        api.request(path,method='DELETE',missing_ok=True);deleted+=1
    print('PUBLIC_SOURCES_REMOVED='+str(deleted))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['plan','backup','delete'])
    parser.add_argument('--items');parser.add_argument('--root',default='backup');parser.add_argument('--remote-id')
    args=parser.parse_args();api=Api()
    if args.mode=='plan':
        request=json.loads(Path('.github/private-output-cleanup-request.json').read_text())
        if request['mode'] not in ('plan','execute'):raise ValueError('Invalid cleanup mode')
        items=inventory(api);batches=make_batches(items)
        counts={'artifacts':sum(x['kind']=='artifact' for x in items),'log_runs':sum(x['kind']=='logs' for x in items),
                'artifact_bytes':sum(x['size'] for x in items if x['kind']=='artifact'),'batches':len(batches)}
        print('PLAN_COUNTS='+json.dumps(counts))
        with open(os.environ['GITHUB_OUTPUT'],'a') as output:
            output.write('execute='+str(request['mode']=='execute' and bool(batches)).lower()+'\n')
            output.write('matrix='+json.dumps({'include':batches or [{'batch':0,'items':[]}]},separators=(',',':'))+'\n')
    elif args.mode=='backup':backup(api,json.loads(args.items),args.root)
    else:delete_after_remote_verification(api,args.root,int(args.remote_id))

if __name__=='__main__':main()
