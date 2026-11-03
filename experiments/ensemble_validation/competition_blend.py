"""Separate fixed 10% same-competition research; never edits locked forecasts."""
import argparse,copy,hashlib,html,json,math
from datetime import date,datetime,timedelta,timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from context_features import fixture_index
from priced_choices import choose,compare,read,write
from conditional_score import football_score,basketball_score

VERSION='competition-blend-10-v1'
FILE='competition-before-results.json'
FIRST='2026-11-04'
WEIGHT=.10

def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def history(matches,ident,team,sport,target):
    start=(date.fromisoformat(target)-timedelta(days=365)).isoformat()
    rows={}
    if not ident or not ident.get('tournamentId'):return []
    for r in matches:
        if r.get('sport')!=sport or str(r.get('tournamentId'))!=str(ident['tournamentId']):continue
        if not start<=r.get('date','')<target or team not in (r['home'],r['away']):continue
        if sport=='basketball' and r['homeScore']==r['awayScore']:continue
        rows[r['key']]=r
    return sorted(rows.values(),key=lambda r:(r['date'],r['key']),reverse=True)[:6]

def estimate(matches,ident,sport,target,line):
    if not ident:return None,[0,0]
    sides=[history(matches,ident,ident[side],sport,target) for side in ('home','away')]
    counts=list(map(len,sides))
    if not all(counts):return None,counts
    markets={};means=[]
    for side,rows in zip(('home','away'),sides):
        gf=[r['homeScore'] if r['home']==ident[side] else r['awayScore'] for r in rows]
        ga=[r['awayScore'] if r['home']==ident[side] else r['homeScore'] for r in rows]
        means.append((sum(gf)/len(rows),sum(ga)/len(rows)))
    for market in (['MS','OU','BTTS'] if sport=='football' else ['MS','OU']):
        values=[]
        for side,rows in zip(('home','away'),sides):
            v=[0.]*(3 if sport=='football' and market=='MS' else 2)
            for r in rows:
                gf=r['homeScore'] if r['home']==ident[side] else r['awayScore']
                ga=r['awayScore'] if r['home']==ident[side] else r['homeScore']
                if market=='MS':
                    # Orient both teams' historical form toward today's home/away outcome.
                    h,a=(gf,ga) if side=='home' else (ga,gf)
                    i=0 if h>a else 1 if sport=='football' and h==a else 2 if sport=='football' else 1
                elif market=='BTTS':i=0 if gf>0 and ga>0 else 1
                else:
                    if not isinstance(line,(int,float)) or not math.isfinite(line) or gf+ga==line:continue
                    i=0 if gf+ga>line else 1
                v[i]+=1
            n=sum(v)
            if not n:break
            values.append([x/n for x in v])
        if len(values)==2:markets[market]=[(a+b)/2 for a,b in zip(*values)]
    return {'markets':markets,'mean':[(means[0][0]+means[1][1])/2,(means[1][0]+means[0][1])/2]},counts

def freeze(root,now=None):
    root=Path(root);path=root/FILE
    base=read(root/'priced-before-results.json');target=base['targetDate']
    if path.exists():
        saved=read(path)
        if saved.get('targetDate')!=target or saved.get('version')!=VERSION:raise ValueError('Research snapshot identity mismatch')
        return saved
    if target<FIRST:return None
    now=now or datetime.now(timezone.utc)
    ledger=read(root/'context-ledger.json')
    index=fixture_index(read(root/'live-history-journal.json'))
    conflicts={tuple(x) for x in ledger.get('identityConflicts',[])}
    for b in ledger.get('identities',[]):
        k=(b['sport'],b['date'],str(b['eventId']))
        if k not in conflicts:index.setdefault(k,b)
    payload=read(root/'stability-model.json')['payload'];systems={};coverage={}
    for sport in ('football','basketball'):
        replay={str(r['eventId']):r for r in read(root/(sport+'-replay.json')) if r['date']==target}
        baseline=copy.deepcopy(base['systems'][sport]['experiment']);candidate=copy.deepcopy(baseline)
        stats={'fixtures':len(candidate),'withContribution':0,'fullTenPercent':0,'missingIdentity':0,'meanWeight':0}
        for ref,e in zip(baseline,candidate):
            key=(sport,target,str(e['eventId']));ident=index.get(key) if key not in conflicts else None
            row=replay[str(e['eventId'])];line=2.5 if sport=='football' else (row.get('odds') or {}).get('hOverUnderValue')
            est,counts=estimate(ledger['matches'],ident,sport,target,line)
            weight=WEIGHT*(min(counts)/6) if est else 0
            if not ident:stats['missingIdentity']+=1
            stats['withContribution']+=int(weight>0);stats['fullTenPercent']+=int(weight==WEIGHT);stats['meanWeight']+=weight
            try:kickoff=datetime.fromisoformat(target+'T'+e['time']).replace(tzinfo=ZoneInfo('Europe/Istanbul'))
            except (KeyError,ValueError,TypeError):kickoff=None
            before=bool(e.get('prospectiveBeforeKickoff') and kickoff and now<kickoff)
            ref['prospectiveBeforeKickoff']=e['prospectiveBeforeKickoff']=before
            e['sameCompetition']={'counts':counts,'weight':weight,'tournamentId':ident.get('tournamentId') if ident else None}
            if weight:
                for market,probs in est['markets'].items():
                    old=e['markets'][market];e['markets'][market]=[(1-weight)*p+weight*q for p,q in zip(old,probs)]
                e['scoreMean']=[(1-weight)*p+weight*q for p,q in zip(e['scoreMean'],est['mean'])]
                e['chosen']=choose(e,row,sport);c=e['chosen']
                if c:
                    sc=football_score(e['scoreMean'],payload['footballDistribution'],c['market'],c['option'],line) if sport=='football' else basketball_score(e['scoreMean'],payload['basketballCovariance'],c['market'],c['option'],line or 0)
                    e['score']=sc['score']
            systems[sport]={'main':baseline,'experiment':candidate}
        stats['meanWeight']/=max(1,len(candidate));coverage[sport]=stats
    b={'version':VERSION,'policy':'available-price-v1','targetDate':target,'createdAt':now.isoformat(),'firstIndependentDate':FIRST,'previewOnly':False,
       'maximumWeight':WEIGHT,'window':6,'lookbackDays':365,'sparsePolicy':'0.10 * min(homeCount,awayCount)/6; missing=0',
       'sourceSha256':digest(root/'priced-before-results.json'),'ledgerSha256':digest(root/'context-ledger.json'),'systems':systems,'coverage':coverage}
    write(path,b);return b

def settle(root):
    root=Path(root);p=root/FILE
    if not p.exists():return None
    b=read(p);result={k:b[k] for k in ('version','targetDate','firstIndependentDate','maximumWeight','coverage','sourceSha256')}
    for name,prospective in [('beforeKickoff',True),('allIncludingLate',False)]:
        result[name]=compare(b,root,prospective)
        for r in result[name]:r['system']='locked' if r['system']=='main' else VERSION
    write(root/'competition-evaluation.json',result)
    rows=''.join('<tr>'+''.join('<td>'+html.escape(str(r[k]))+'</td>' for k in ('sport','system','fraction','hits','count','accuracy','brier','logLoss','scoreMAE'))+'</tr>' for r in result['beforeKickoff'])
    page='<!doctype html><html lang="tr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Aynı lig/kupa · %10 deneyi</title><style>body{font:14px system-ui;margin:12px}main{overflow:auto}td,th{padding:8px;border-bottom:1px solid #ddd}table{border-collapse:collapse}</style><h1>Aynı lig/kupa · %10 deneyi</h1><p>'+b['targetDate']+' · Ana tercihler değişmez. İlk bağımsız gün: '+FIRST+'. Eksik geçmişte katkı azalır. Maç öncesi, oranlı tercihler; ana ölçü ilk %50.</p><main><table><tr>'+''.join('<th>'+x+'</th>' for x in ('Spor','Sistem','Grup','İsabet','N','Başarı','Brier','Log loss','Skor MAE'))+'</tr>'+rows+'</table></main></html>'
    (root/'ayni-lig-deneyi.html').write_text(page);return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['freeze','settle']);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    (freeze if a.mode=='freeze' else settle)(a.output)
