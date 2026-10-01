"""Freeze inputs and vary history features. Never use outcomes to build features."""
import argparse
import copy
import hashlib
import json
import math
from datetime import date, datetime
from pathlib import Path

MONTHS={m:i+1 for i,m in enumerate('Ocak Şubat Mart Nisan Mayıs Haziran Temmuz Ağustos Eylül Ekim Kasım Aralık'.split())}
MONTHS.update({m[:3]:i for m,i in list(MONTHS.items())})
PROFILES={
 'six-balanced':(False,True,True,True),
 'six-simple':(False,False,False,False),
 'six-no-recency':(False,False,True,True),
 'six-no-venue':(False,True,False,True),
 'six-no-form':(False,True,True,True),
 'wide-simple':(True,False,False,False),
 'wide-recency':(True,True,False,False),
 'wide-venue':(True,False,True,False),
 'wide-balanced':(True,True,True,True),
 'wide-no-recency':(True,False,True,True),
 'wide-no-venue':(True,True,False,True),
 'wide-no-form':(True,True,True,True),
}

def dump(path,value):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')

def read_date(s,anchor=None):
 try:return date.fromisoformat(s[:10])
 except (ValueError,TypeError):pass
 p=str(s).split()
 if len(p)==2 and anchor is not None:
  try:
   d=date(anchor.year,MONTHS[p[1]],int(p[0]))
   return d if d<=anchor else date(anchor.year-1,MONTHS[p[1]],int(p[0]))
  except (ValueError,KeyError):return None
 try:return date(int(p[2]),MONTHS[p[1]],int(p[0]))
 except (ValueError,KeyError,IndexError):return None

def friendly(s):return str(s).casefold()=='haz' or any(k in str(s).casefold() for k in ('hazırlık','friendly','preseason'))

def archived(rows,team,cutoff,sport):
 out=[];anchor=cutoff
 for r in rows:
  raw_date=r.get('matchDate');d=read_date(raw_date,anchor)
  if not d or d>=cutoff or r.get('status','finished')!='finished':continue
  if r.get('homeTeam')==team:venue,gf,ga='home',r['homeScore'],r['awayScore']
  elif r.get('awayTeam')==team:venue,gf,ga='away',r['awayScore'],r['homeScore']
  else:continue
  inferred=len(str(raw_date).split())==2
  if inferred:anchor=d
  known=sport=='football' or gf!=ga
  out.append({'id':'|'.join(str(r.get(k)) for k in ('matchDate','homeTeam','awayTeam')),
              'date':d.isoformat(),'venue':venue,'for':gf,'against':ga,
              'win':int(gf>ga) if known else None,'draw':int(gf==ga) if known else None,
              'tournament':r.get('tournament',''),'source':'frozen-six',
              'rawDate':raw_date,'dateInferred':inferred})
 return sorted({r['id']:r for r in out}.values(),key=lambda r:r['date'],reverse=True)

def filtered(rows,cutoff,limit):
 return sorted({r['id']:r for r in rows if date.fromisoformat(r['date'])<cutoff}.values(),key=lambda r:r['date'],reverse=True)[:limit]

def weighted_stats(rows,cutoff,sport,venue,recency,venue_split,recent_mix,no_form=False):
 half_life=90 if sport=='football' else 60
 def weight(r):
  age=(cutoff-date.fromisoformat(r['date'])).days
  return (2**(-age/half_life) if recency else 1)*(0.25 if friendly(r['tournament']) else 1)
 pairs=[(r,weight(r)) for r in rows]
 def mean(key,pairs,fallback):
  valid=[(r[key],w) for r,w in pairs if r.get(key) is not None]
  total=sum(w for v,w in valid)
  return sum(v*w for v,w in valid)/total if total else fallback
 gf,ga=mean('for',pairs,0),mean('against',pairs,0)
 relevant=[(r,w) for r,w in pairs if r['venue']==venue]
 sw=sum(w for r,w in relevant)
 # Shrink only the sparse venue estimate toward this team's general estimate.
 vf=(sum(r['for']*w for r,w in relevant)+4*gf)/(sw+4)
 va=(sum(r['against']*w for r,w in relevant)+4*ga)/(sw+4)
 rf,ra=mean('for',pairs[:6],gf),mean('against',pairs[:6],ga)
 v=0.35 if venue_split else 0;f=0.25 if recent_mix else 0
 avgf=(1-v-f)*gf+v*vf+f*rf;avga=(1-v-f)*ga+v*va+f*ra
 points=[(dict(r,points=(3*r['win']+r['draw']) if sport=='football' else 1+r['win']),w)
         for r,w in pairs[:6] if r.get('win') is not None]
 ppg=mean('points',points,1 if sport=='football' else 1.5)
 if no_form:ppg=1 if sport=='football' else 1.5
 total=sum(w for r,w in pairs)
 ess=total*total/sum(w*w for r,w in pairs) if total else 0
 audit={'count':len(rows),'effectiveCount':ess,'venueCount':len(relevant),
        'inferredDateCount':sum(r.get('dateInferred',False) for r in rows),
        'unknownFinalCount':sum(r.get('win') is None for r in rows),'rows':rows}
 if sport=='football':
  count=len(points)
  share=avgf/(avgf+avga) if avgf+avga else 0.5
  stats={'avgGF':avgf,'avgGA':avga,'last5Count':count,'last5Points':ppg*count,
         'avgPointsPerMatch':ppg,'rating100':math.floor(max(0,min(100,ppg/3*60+share*40))+0.5)}
 else:stats={'avgPointsFor':avgf,'avgPointsAgainst':avga,'avgTotalPoints':avgf+avga,'ppg':ppg}
 return stats,audit

def assemble(sources,reference,output,holdout):
 pool={}
 for r in json.loads((reference/'predictions.json').read_text()):
  for team,key in ((r['homeTeam'],'homeStats'),(r['awayTeam'],'awayStats')):
   pool[(r['sport'],team)]=r['new'][key]['rows']
 days={}
 for root in sources:
  for sport,folder in (('football','futbol'),('basketball','basketbol')):
   for p in (root/folder/'data').glob('MatchInfo-????-??-??.json'):
    d=p.stem[len('MatchInfo-'):]
    if d<=holdout:days[(sport,d)]=(root,folder)
 records={'football':[],'basketball':[]}; hashes={};excluded=[]
 for (sport,d),(root,folder) in sorted(days.items()):
  files={k:root/folder/'data'/f'{k}-{d}.json' for k in ('MatchInfo','TeamMatchHistory','Match','PredictionResult','RealScores')}
  data={k:json.loads(p.read_text()) if p.exists() else [] for k,p in files.items()}
  for k,p in files.items():
   if p.exists():hashes[f'{root.name}/{folder}/{p.name}']=hashlib.sha256(p.read_bytes()).hexdigest()
  histories={str(r.get('originalMatchUrl',r.get('detailUrl',''))).rstrip('/').split('/')[-1]:r for r in data['TeamMatchHistory']}
  matches={(m['homeTeam'],m['awayTeam']):m for m in data['Match']}
  predictions={(m['homeTeam'],m['awayTeam']):m for m in data['PredictionResult']}
  real={' - '.join((r['homeTeam'],r['awayTeam'])):r['score'] for r in data['RealScores']}
  for info in data['MatchInfo']:
   eid=info['detailUrl'].rstrip('/').split('/')[-1];h=histories.get(eid)
   if not h:excluded.append({'sport':sport,'date':d,'eventId':eid,'reason':'history absent'});continue
   key=h['teamEv'],h['teamDep'];base=matches.get(key);published=predictions.get(key)
   if base is None or published is None:raise ValueError(f'Frozen baseline absent: {sport} {d} {eid}')
   base=copy.deepcopy(base);base['odds']=info['odds']
   cutoff=date.fromisoformat(d)
   six=[archived(h.get(k,[]),team,cutoff,sport) for k,team in zip(('sonMaclarHome','sonMaclarAway'),key)]
   wide=[filtered(pool.get((sport,team),[]),cutoff,20 if sport=='football' else 25) for team in key]
   wide_ok=all(len(w)>=len(s) and len(w)>0 for w,s in zip(wide,six))
   variants={'legacy':{'match':base,'audit':{'kind':'exact saved Match JSON'}}}
   no_h2h=copy.deepcopy(base)
   if sport=='football':
    for side in ('homeStats','awayStats'):
     for prop in ('h2hCount','h2hWins','h2hWinRate'):no_h2h[side][prop]=0
   else:
    for prop in ('avgPointsForHome','avgPointsForAway','h2hAvgTotalPoints'):no_h2h[prop]=0
   variants['legacy-no-h2h']={'match':no_h2h,'audit':{'kind':'H2H removal only'}}
   for name,(use_wide,decay,venue,mix) in PROFILES.items():
    if use_wide and not wide_ok:continue
    selected=wide if use_wide else six
    if use_wide and not all(selected):continue
    match=copy.deepcopy(base);audits=[]
    for side,rows,v in zip(('homeStats','awayStats'),selected,('home','away')):
     if not rows:
      audits.append({'count':0,'fallback':'unchanged frozen baseline stats; no exact-name dated rows'})
      continue
     st,audit=weighted_stats(rows,cutoff,sport,v,decay,venue,mix,name.endswith('-no-form'))
     match[side].update(st);audits.append(audit)
    variants[name]={'match':match,'audit':{'home':audits[0],'away':audits[1],
                                        'historicalWideScope':'exact team-name overlap with frozen 1 October history pool; no future rows'}}
   records[sport].append({'date':d,'eventId':eid,'name':info['name'],'time':info['time'],
                         'role':'holdout' if d==holdout else 'training','odds':info['odds'],
                         'published':published,'realScore':real.get(info['name']),'wideAvailable':wide_ok,'variants':variants})
 for sport,rows in records.items():dump(output/(sport+'-inputs.json'),rows)
 dump(output/'input-manifest.json',{'holdoutDate':holdout,'hashes':hashes,'excluded':excluded,
      'counts':{s:len(r) for s,r in records.items()},'futureDataPolicy':'features strictly before fixture date; holdout outcomes never select weights',
      'wideLimitation':'Older expanded history exists only for teams present in the frozen 1 October artifact. Paired comparisons report their own cohort.'})
 return records

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--published',type=Path,required=True);p.add_argument('--archive',type=Path,required=True)
 p.add_argument('--reference',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--holdout',default='2026-10-01')
 a=p.parse_args();assemble([a.archive,a.published],a.reference,a.output,a.holdout)
