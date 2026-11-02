"""Frozen offered-price selection layer over unchanged locked model probabilities."""
import argparse,copy,hashlib,json,math
from pathlib import Path
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from display_odds import KEYS,valid_number
from report import GROUPS,result,parse_score,wilson

FILE='priced-before-results.json'
POLICY='available-price-v1'
def read(p):return json.loads(Path(p).read_text())
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def signature(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def choose(entry,row,sport):
    options=[];odds=row.get('odds') or {}
    for market,keys in KEYS[sport].items():
        probabilities=entry.get('markets',{}).get(market,[])
        if market=='OU' and sport=='basketball' and not valid_number(odds.get('hOverUnderValue'),0):continue
        for i,key in enumerate(keys):
            if i>=len(probabilities):continue
            p=probabilities[i];price=odds.get(key)
            if isinstance(p,bool) or not isinstance(p,(int,float)) or not math.isfinite(p) or not 0<=p<=1:continue
            if valid_number(price,1):options.append({'market':market,'option':i,'confidence':p,'price':price})
    return max(options,key=lambda x:x['confidence']) if options else None

def freeze(root,now=None):
    root=Path(root);path=root/FILE
    model=root/'stability-model.json';locked=root/'stability-before-results.json'
    source=locked if locked.exists() else root/'context-before-results.json'
    book=read(source);target=book['targetDate'];preview=not locked.exists()
    if preview and target!='2026-10-18':raise ValueError('Missing locked snapshot')
    if path.exists():
        saved=read(path);body={k:v for k,v in saved.items() if k!='snapshotSha256'}
        if saved['snapshotSha256']!=signature(body) or saved['sourceSha256']!=digest(source) or saved['modelSha256']!=digest(model) or saved['policy']!=POLICY:raise ValueError('Frozen priced choices changed')
        return saved
    now=now or datetime.now(timezone.utc);payload=read(model)['payload'];systems={}
    from conditional_score import football_score,basketball_score
    for sport in GROUPS:
        labels={str(r['eventId']):r for r in read(root/(sport+'-replay.json')) if r['date']==target};systems[sport]={}
        for name in ['main','opponent' if preview else book['version']]:
            out=[]
            for original in book['systems'][sport].get(name,[]):
                e=copy.deepcopy(original);row=labels.get(str(e['eventId']))
                if row is None:raise ValueError('Missing priced fixture input')
                c=choose(e,row,sport);e['chosen']=c
                try:before=now<datetime.fromisoformat(target+'T'+e['time']).replace(tzinfo=ZoneInfo('Europe/Istanbul'))
                except (ValueError,KeyError,TypeError):before=False
                e['prospectiveBeforeKickoff']=bool(not preview and before and e.get('prospectiveBeforeKickoff'))
                if c and name!='main':
                    mean=e.get('scoreMean')
                    if mean is None:raise ValueError('Missing conditional score mean')
                    line=2.5 if sport=='football' else row['odds']['hOverUnderValue'] if c['market']=='OU' else 0
                    sc=football_score(mean,payload['footballDistribution'],c['market'],c['option'],line) if sport=='football' else basketball_score(mean,payload['basketballCovariance'],c['market'],c['option'],line)
                    e['score']=sc['score']
                out.append(e)
            systems[sport]['main' if name=='main' else 'experiment']=out
    saved={'policy':POLICY,'targetDate':target,'createdAt':now.isoformat(),'previewOnly':preview,'sourceSha256':digest(source),'modelSha256':digest(model),'systems':systems}
    saved['snapshotSha256']=signature(saved);write(path,saved);return saved

def compare(book,root,prospective):
    blocks=[]
    for sport,systems in book['systems'].items():
        rows={str(r['eventId']):r for r in read(Path(root)/(sport+'-replay.json')) if r['date']==book['targetDate']}
        selected={name:{str(e['eventId']):e for e in es if e['chosen'] and (not prospective or e['prospectiveBeforeKickoff'])} for name,es in systems.items()}
        common=set.intersection(*(set(v) for v in selected.values())) if selected else set()
        complete={i for i in common if all(result(rows[i],sport,es[i]['chosen']['market']) is not None for es in selected.values())}
        for name,es in selected.items():
            ranked=sorted([es[i] for i in common],key=lambda e:(-e['chosen']['confidence'],str(e['eventId'])))
            for fraction in [.25,.5,.75,1.]:
                group=ranked[:math.ceil(len(ranked)*fraction)];items=[e for e in group if str(e['eventId']) in complete];n=len(items)
                hit=[int(result(rows[str(e['eventId'])],sport,e['chosen']['market'])==e['chosen']['option']) for e in items];p=[e['chosen']['confidence'] for e in items];errors=[]
                for e in items:
                    actual=parse_score({'scoreline':rows[str(e['eventId'])].get('realScore')})
                    if actual is not None and e.get('score'):errors.append(sum(abs(a-b) for a,b in zip(actual,e['score']))/2)
                blocks.append({'sport':sport,'system':name,'fraction':fraction,'plannedCount':len(group),'count':n,'hits':sum(hit),'accuracy':sum(hit)/n if n else None,'interval95':wilson(sum(hit),n) if n else None,'brier':sum((a-b)**2 for a,b in zip(p,hit))/n if n else None,'logLoss':-sum(math.log(max(1e-12,a if b else 1-a)) for a,b in zip(p,hit))/n if n else None,'scoreMAE':sum(errors)/len(errors) if errors else None,'scoreCount':len(errors)})
    return blocks

def settle(root):
    root=Path(root);book=freeze(root)
    report={'policy':POLICY,'targetDate':book['targetDate'],'createdAt':book['createdAt'],'snapshotSha256':book['snapshotSha256'],'previewOnly':book['previewOnly'],'beforeKickoff':compare(book,root,True),'allIncludingLate':compare(book,root,False),'coverage':{s:{k:{'fixtures':len(es),'noPricedChoice':sum(e['chosen'] is None for e in es)} for k,es in ss.items()} for s,ss in book['systems'].items()}}
    write(root/'priced-evaluation.json',report);return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['freeze','settle']);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    (freeze if a.mode=='freeze' else settle)(a.output)
