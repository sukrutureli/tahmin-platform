"""Immutable before-result predictions and later paired settlement, artifact-only."""
import argparse
import hashlib
import json
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from prepare import dump
from report import BASE,GROUPS,today_rule_vector,score_value,result,metrics,parse_score,page,table,pct


def freeze(data,previous):
 dates={r['date'] for rows in data.values() for r in rows if r['role']=='holdout'}
 if len(dates)!=1:raise ValueError('Exactly one target day is required')
 target=next(iter(dates));learned=previous.get('derivedFromDate','') if previous else ''
 usable=bool(learned and learned<target and previous.get('validFromDate','9999')<=target)
 out={'targetDate':target,'createdAt':datetime.now(timezone.utc).isoformat(),'derivedFromDate':learned or None,
      'independentRuleAvailable':usable,'status':'earlier-day frozen rule' if usable else 'baseline only: no earlier frozen rule',
      'previousRuleHash':hashlib.sha256(json.dumps(previous,sort_keys=True).encode()).hexdigest(),'predictions':[]}
 for sport,rows in data.items():
  for row in rows:
   if row['role']!='holdout':continue
   try:
    kickoff=datetime.fromisoformat(target+'T'+row['time']).replace(tzinfo=ZoneInfo('Europe/Istanbul'))
    prospective=datetime.fromisoformat(out['createdAt'])<kickoff
   except (ValueError,KeyError):prospective=False
   entry={'prospectiveBeforeKickoff':prospective,'sport':sport,'date':target,'eventId':row['eventId'],'name':row['name'],'odds':row['odds'],'markets':{}}
   for market in GROUPS[sport]:
    base=('legacy',BASE[sport],0)
    rule=previous.get('rules',{}).get(sport,{}).get('markets',{}).get(market,{}).get('rule') if usable else None
    candidate=tuple(rule['candidate']) if rule else base
    entry['markets'][market]={'candidate':list(candidate),'baseline':today_rule_vector(row,sport,market,base),'probabilities':today_rule_vector(row,sport,market,candidate)}
   old_score=previous.get('rules',{}).get(sport,{}).get('scores',{}).get('rule') if usable else None
   candidate=tuple(old_score['candidate']) if old_score else ('legacy',BASE[sport])
   baseline=score_value(row,sport,('legacy',BASE[sport]))
   entry['score']={'candidate':list(candidate),'baseline':baseline,'prediction':score_value(row,sport,candidate) or baseline}
   out['predictions'].append(entry)
 return out


def settle(book,data,previous_journal=None):
 labels={(sport,r['date'],r['eventId']):r for sport,rows in data.items() for r in rows}
 summary={'date':book['targetDate'],'ruleLearnedOn':book['derivedFromDate'],'independentRuleAvailable':book['independentRuleAvailable'],'markets':[],'scores':[]}
 for sport,markets in GROUPS.items():
  entries=[e for e in book['predictions'] if e['sport']==sport]
  for market,names in markets.items():
   old=[];new=[];prospective_old=[];prospective_new=[]
   for e in entries:
    row=labels.get((sport,e['date'],e['eventId']));y=result(row,sport,market) if row else None
    p=e['markets'][market]
    if y is not None and p['baseline'] is not None and p['probabilities'] is not None:
     old.append((p['baseline'],y));new.append((p['probabilities'],y))
     if e.get('prospectiveBeforeKickoff',False):
      prospective_old.append((p['baseline'],y));prospective_new.append((p['probabilities'],y))
   summary['markets'].append({'sport':sport,'market':market,'baseline':metrics(old,names),'frozenRule':metrics(new,names),'prospectiveBaseline':metrics(prospective_old,names),'prospectiveFrozenRule':metrics(prospective_new,names)})
  score_pairs=[]
  for e in entries:
   row=labels.get((sport,e['date'],e['eventId']));actual=parse_score({'scoreline':row.get('realScore')}) if row else None
   if actual and e['score']['baseline'] and e['score']['prediction']:score_pairs.append((e['score'],actual))
  if score_pairs:
   mae=lambda key:sum((abs(p[key][0]-y[0])+abs(p[key][1]-y[1]))/2 for p,y in score_pairs)/len(score_pairs)
   summary['scores'].append({'sport':sport,'count':len(score_pairs),'baselineTeamMAE':mae('baseline'),'frozenRuleTeamMAE':mae('prediction')})
 journal=[x for x in (previous_journal or []) if x['date']!=summary['date']]+[summary]
 return summary,sorted(journal,key=lambda x:x['date'])

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['freeze','settle']);p.add_argument('--output',type=Path,required=True);p.add_argument('--previous',type=Path,required=True);a=p.parse_args()
 data={s:json.loads((a.output/(s+'-replay.json')).read_text()) for s in BASE}
 bookpath=a.output/'before-results-predictions.json'
 if a.mode=='freeze':
  previous_path=a.previous/'frozen-today-rules.json';previous=json.loads(previous_path.read_text()) if previous_path.exists() else {}
  saved=a.previous/'before-results-predictions.json'
  target={r['date'] for rows in data.values() for r in rows if r['role']=='holdout'}
  oldbook=json.loads(saved.read_text()) if saved.exists() else None
  if oldbook and target=={oldbook.get('targetDate')}:
   bookpath.write_bytes(saved.read_bytes())
   print('Reused immutable prediction snapshot for '+oldbook['targetDate'])
  else:dump(bookpath,freeze(data,previous))
 else:
  raw=bookpath.read_bytes();book=json.loads(raw)
  old=a.previous/'daily-journal.json';journal=json.loads(old.read_text()) if old.exists() else []
  summary,journal=settle(book,data,journal);summary['predictionFileSha256']=hashlib.sha256(raw).hexdigest()
  dump(a.output/'daily-evaluation.json',summary);dump(a.output/'daily-journal.json',journal)
  body='<p>Her gün yalnız daha önceki günden kaydedilen kurallar sınanır. Bugünden öğrenilen kural yarının adayıdır. Maç başladıktan sonra yapılan hesaplar geriye dönük kontrol olarak kalır; başlamadan kaydedilen N ayrıca gösterilir. İlk gün eski kural yoksa baseline gösterilir ve bağımsız başarı iddia edilmez. Tarihlerde tamamlanmış maç sayısı değişebilir.</p>'
  lines=[]
  for day in journal:
   for m in day['markets']:
    b=m['baseline'];n=m['frozenRule']
    if b and n:lines.append((day['date'],m['sport'],m['market'],b['count'],pct(b['accuracy']),pct(n['accuracy']),m['prospectiveFrozenRule']['count'] if m['prospectiveFrozenRule'] else 0,day['ruleLearnedOn'] or 'Yok','Evet' if day['independentRuleAvailable'] else 'Hayır'))
  body+=table(['Gün','Spor','Pazar','N','Mevcut isabet','Önceki kural isabeti','Başlamadan kaydedilen N','Kural öğrenme günü','Bağımsız gün'],lines)
  (a.output/'day-by-day.html').write_text(page('Gün gün bağımsız değerlendirme',body),encoding='utf-8')
