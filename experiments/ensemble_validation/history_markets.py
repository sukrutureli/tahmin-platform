"""Experimental goal/total features from pre-fixture history only; no labels read."""
import argparse
import copy
import json
import math
from pathlib import Path
from prepare import dump, friendly

BASE={'football':'EnsembleModel','basketball':'BasketEnsembleModel'}

def features(rows):
 if not rows:return None
 pairs=[(r,.25 if friendly(r.get('tournament','')) else 1.0) for r in rows]
 n=sum(w for r,w in pairs)
 def mean(f):return sum(w*f(r) for r,w in pairs)/n
 def rate(f):return (1+sum(w*int(f(r)) for r,w in pairs))/(2+n)
 total=mean(lambda r:r['for']+r['against'])
 return {'count':len(rows),'weightCount':n,'goalsFor':mean(lambda r:r['for']),
         'goalsAgainst':mean(lambda r:r['against']),
         'scoresRate':rate(lambda r:r['for']>0),'concedesRate':rate(lambda r:r['against']>0),
         'blankRate':rate(lambda r:r['for']==0),'cleanSheetRate':rate(lambda r:r['against']==0),
         'over25Rate':rate(lambda r:r['for']+r['against']>2.5),
         'bttsRate':rate(lambda r:r['for']>0 and r['against']>0),
         'totalMean':total,'totalVariance':mean(lambda r:(r['for']+r['against']-total)**2)}

def enrich(rows,sport):
 for row in rows:
  for variant,entry in row['variants'].items():
   audit=entry.get('audit',{})
   h=features(audit.get('home',{}).get('rows',[]));a=features(audit.get('away',{}).get('rows',[]))
   if not h or not a:continue
   # Fail closed: a history from the target day cannot become a predictor.
   for side in ('home','away'):
    if any(r['date']>=row['date'] for r in audit[side]['rows']):raise ValueError('Future history in market features')
   entry['marketFeatureAudit']={'home':h,'away':a,'usesOutcomes':False,'smoothing':'Beta(1,1) for observed event frequencies'}
   base=entry['models'][BASE[sport]]
   total=copy.deepcopy(base)
   expected_home=.5*(h['goalsFor']+a['goalsAgainst'])
   expected_away=.5*(a['goalsFor']+h['goalsAgainst'])
   total['scoreline']=f'{math.floor(expected_home+.5)}-{math.floor(expected_away+.5)}'
   if sport=='football':
    # Three-way triangulation: observed totals, attack/defence mean and Poisson total.
    lam=expected_home+expected_away
    poisson=1-math.exp(-lam)*(1+lam+lam*lam/2)
    total['pOver25']=.5*poisson+.25*h['over25Rate']+.25*a['over25Rate']
    btts=copy.deepcopy(base)
    home_scores=.5*(h['scoresRate']+a['concedesRate'])
    away_scores=.5*(a['scoresRate']+h['concedesRate'])
    btts['pBttsYes']=.5*home_scores*away_scores+.25*h['bttsRate']+.25*a['bttsRate']
    btts['scoreline']=''
    entry['models']['HistoryBttsModel']=btts
   else:
    line=row['odds'].get('hOverUnderValue',0)
    if line<=0:continue
    # Match-total variance, not an assumed universal scoring spread.
    sigma=max(8.0,math.sqrt((h['totalVariance']+a['totalVariance'])/2))
    total['pOver25']=.5*(1+math.erf((expected_home+expected_away-line)/(sigma*math.sqrt(2))))
    entry['marketFeatureAudit']['totalSigma']=sigma
   entry['models']['HistoryTotalsModel']=total
 return rows

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args()
 for sport in BASE:
  path=args.output/(sport+'-replay.json')
  dump(path,enrich(json.loads(path.read_text()),sport))
