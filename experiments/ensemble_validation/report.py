"""Fit candidate choices on previous dates, evaluate once on held-out date."""
import argparse
import html
import json
import math
import re
import statistics
from datetime import date,datetime,timedelta,timezone
from pathlib import Path
from prepare import dump

GROUPS={'football':{'MS':['MS1','MSX','MS2'],'OU':['Üst','Alt'],'BTTS':['Var','Yok']},
        'basketball':{'MS':['MS1','MS2'],'OU':['Üst','Alt']}}
BASE={'football':'EnsembleModel','basketball':'BasketEnsembleModel'}

def vector(p,sport,market):
 if market=='MS':v=[p['pHome'],p['pDraw'],p['pAway']] if sport=='football' else [p['pHome'],p['pAway']]
 elif market=='OU':v=[p['pOver25'],1-p['pOver25']]
 else:v=[p['pBttsYes'],1-p['pBttsYes']]
 if not all(isinstance(x,(int,float)) and math.isfinite(x) and 0<=x<=1 for x in v):raise ValueError('Invalid probability')
 return [x/sum(v) for x in v] if sum(v)>0 else [1/len(v)]*len(v)

def allowed(sport,model,market):
 if model in ('HistoryBttsModel','HistoryCoupledBttsModel'):return sport=='football' and market=='BTTS'
 if model=='HistoryTotalsModel':return market=='OU'
 if model=='VarianceShrinkTotalsModel':return sport=='basketball' and market=='OU'
 return not(sport=='football' and model in ('FormMomentumModel','ValidOddsFormModel') and market!='MS')

def result(row,sport,market):
 m=re.fullmatch(r'(\d+)\s*[-–]\s*(\d+)',str(row.get('realScore','')))
 if not m:return None
 h,a=map(int,m.groups())
 if sport=='basketball' and h==a:return None
 if market=='MS':return 0 if h>a else (1 if sport=='football' and h==a else 2 if sport=='football' else 1)
 if market=='BTTS':return 0 if h>0 and a>0 else 1
 line=2.5 if sport=='football' else row['odds'].get('hOverUnderValue',0)
 if line<=0 or h+a==line:return None
 return 0 if h+a>line else 1

def candidate_vector(row,sport,market,candidate):
 variant,model,blend=candidate
 models=row['variants'].get(variant,{}).get('models',{})
 if model not in models:return None
 try:
  p=vector(models[model],sport,market)
  if blend:
   base=vector(models[BASE[sport]],sport,market)
   p=[(1-blend)*b+blend*x for b,x in zip(base,p)]
 except (ValueError,TypeError,KeyError):
  return None
 return p

def wilson(hits,n):
 if not n:return None
 z=1.96;p=hits/n;d=1+z*z/n
 center=(p+z*z/(2*n))/d;half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
 return [max(0,center-half),min(1,center+half)]

def metrics(items,labels,threshold=0):
 if not items:return None
 hits=sum(max(range(len(p)),key=lambda i:p[i])==y for p,y in items)
 selected=[(p,y) for p,y in items if max(p)>=threshold]
 successes=sum(max(range(len(p)),key=lambda i:p[i])==y for p,y in selected)
 options=[]
 for i,label in enumerate(labels):
  predicted=[(p,y) for p,y in selected if max(range(len(p)),key=lambda k:p[k])==i]
  correct=sum(y==i for p,y in predicted)
  options.append({'option':label,'predictedCount':len(predicted),'hits':correct,
                  'precision':correct/len(predicted) if predicted else None,'interval95':wilson(correct,len(predicted)),
                  'brier':statistics.mean((p[i]-int(y==i))**2 for p,y in items)})
 return {'count':len(items),'accuracy':hits/len(items),'accuracyInterval95':wilson(hits,len(items)),
         'brier':statistics.mean(sum((p[i]-int(y==i))**2 for i in range(len(p))) for p,y in items),
         'logLoss':statistics.mean(-math.log(max(p[y],1e-12)) for p,y in items),
         'threshold':threshold,'selectedCount':len(selected),'coverage':len(selected)/len(items),
         'selectedAccuracy':successes/len(selected) if selected else None,'options':options}

def samples(rows,sport,market,candidate):
 out=[]
 for r in rows:
  y=result(r,sport,market);p=candidate_vector(r,sport,market,candidate)
  if y is not None and p is not None:out.append((p,y))
 return out

def fit(rows,sport,market):
 labels=GROUPS[sport][market];base=('legacy',BASE[sport],0)
 base_items=samples(rows,sport,market,base)
 candidates={base}
 for r in rows:
  for v,entry in r['variants'].items():
   if v=='legacy-no-h2h' or v.startswith('wide'):continue
   candidates.add((v,BASE[sport],0))
   for model in entry['models']:
    if model!=BASE[sport] and allowed(sport,model,market):
     # Preserve at least half of the actual ensemble; don't replace it with a single model.
     for blend in (0.25,0.5):candidates.add((v,model,blend))
 scored=[];excluded=[]
 for c in sorted(candidates):
  items=samples(rows,sport,market,c)
  if len(items)!=len(base_items) or not items:
   excluded.append({'candidate':list(c),'validSettledCount':len(items),'requiredCount':len(base_items),'reason':'incomplete paired training coverage'})
   continue
  m=metrics(items,labels);scored.append((m['logLoss'],c,m))
 if not scored:return {'candidate':list(base),'threshold':0,'training':None,'eligible':False}
 eligible=len(base_items)>=30 and len({r['date'] for r in rows})>=2
 chosen=min(scored,key=lambda x:(x[0],x[1])) if eligible else next(x for x in scored if x[1]==base)
 items=samples(rows,sport,market,chosen[1])
 # Precision must be reported together with coverage; avoid a one-match '100%' winner.
 thresholds=(0.4,0.5,0.55,0.6,0.65,0.7,0.75) if market=='MS' and sport=='football' else (0.5,0.55,0.6,0.65,0.7,0.75)
 feasible=[metrics(items,labels,t) for t in thresholds]
 feasible=[m for m in feasible if m['selectedCount']>=20 and m['coverage']>=0.25]
 policy=max(feasible,key=lambda m:(m['selectedAccuracy'],m['coverage'])) if feasible and eligible else metrics(items,labels,0)
 return {'candidate':list(chosen[1]),'threshold':policy['threshold'],'training':policy,'eligible':eligible,
         'trainingLeaderboard':[{'candidate':list(c),'metrics':m} for loss,c,m in sorted(scored,key=lambda x:x[0])],
         'excludedCandidates':excluded,
         'status':'exploratory; two training dates cannot establish optimality'}

def parse_score(p):
 m=re.fullmatch(r'(\d+)\s*[-–]\s*(\d+)',str(p.get('scoreline','')))
 return tuple(map(float,m.groups())) if m else None

def poisson_expectation(match):
 h,a=match['homeStats'],match['awayStats'];clamp=lambda x,lo,hi:max(lo,min(hi,x))
 hp=h.get('avgPointsPerMatch',0);ap=a.get('avgPointsPerMatch',0)
 advantage=clamp(1.1*clamp(1+(h.get('rating100',0)-a.get('rating100',0))/600,.85,1.15)*clamp(1+(hp-ap)/5,.75,1.25),.85,1.35)
 lh=max(.1,advantage*(.55*h['avgGF']*clamp(1+.1*(hp-1),.85,1.15)+.45*a['avgGA']))
 la=max(.1,.55*a['avgGF']*clamp(1+.1*(ap-1),.85,1.15)+.45*h['avgGA'])
 return lh,la

def score_value(row,sport,candidate):
 variant,model=candidate;entry=row['variants'].get(variant)
 if entry is None:return None
 if model=='PoissonExpectation':return poisson_expectation(entry['match'])
 if model not in entry['models']:return None
 return parse_score(entry['models'][model])

def score_metrics(rows,sport,candidate):
 data=[]
 for r in rows:
  actual=parse_score({'scoreline':r.get('realScore')});pred=score_value(r,sport,candidate)
  if actual is not None and pred is not None:data.append((pred,actual))
 if not data:return None
 return {'count':len(data),'teamMAE':statistics.mean((abs(p[0]-y[0])+abs(p[1]-y[1]))/2 for p,y in data),
         'teamRMSE':math.sqrt(statistics.mean(((p[0]-y[0])**2+(p[1]-y[1])**2)/2 for p,y in data)),
         'totalMAE':statistics.mean(abs(sum(p)-sum(y)) for p,y in data),
         'marginMAE':statistics.mean(abs(p[0]-p[1]-y[0]+y[1]) for p,y in data),
         'exactRoundedScoreRate':statistics.mean(tuple(math.floor(x+.5) for x in p)==y for p,y in data)}

def today_rule_vector(row,sport,market,candidate):
 # A frozen rule must specify its missing-history behavior before tomorrow's outcomes.
 return candidate_vector(row,sport,market,candidate) or candidate_vector(row,sport,market,('legacy',BASE[sport],0))

def score_rule_metrics(rows,sport,candidate):
 data=[];base=('legacy',BASE[sport])
 for r in rows:
  actual=parse_score({'scoreline':r.get('realScore')})
  fallback=score_value(r,sport,base)
  pred=score_value(r,sport,candidate) or fallback
  if actual is not None and fallback is not None and pred is not None:data.append((pred,actual))
 if not data:return None
 return {'count':len(data),'teamMAE':statistics.mean((abs(p[0]-y[0])+abs(p[1]-y[1]))/2 for p,y in data),
         'teamRMSE':math.sqrt(statistics.mean(((p[0]-y[0])**2+(p[1]-y[1])**2)/2 for p,y in data)),
         'totalMAE':statistics.mean(abs(sum(p)-sum(y)) for p,y in data),
         'marginMAE':statistics.mean(abs(p[0]-p[1]-y[0]+y[1]) for p,y in data),
         'exactRoundedScoreRate':statistics.mean(tuple(math.floor(x+.5) for x in p)==y for p,y in data)}

def derive_today_rules(rows,sport):
 today=[r for r in rows if r['role']=='holdout']
 completed=[r for r in rows if r.get('realScore')]
 rules={'purpose':'Rules selected through today for a later independent test. The latest day is training here, never validation.',
        'autoPromotion':False,'sampleWarning':'Candidates must not lower hit rate on any completed source day; this still does not establish optimality.',
        'fallback':'unchanged legacy ensemble when the selected variant/model is unavailable or invalid',
        'markets':{},'scores':{}}
 for market,labels in GROUPS[sport].items():
  base=('legacy',BASE[sport],0);candidates={base}
  for r in completed:
   for variant,entry in r['variants'].items():
    candidates.add((variant,BASE[sport],0))
    for model in entry['models']:
     if model!=BASE[sport] and allowed(sport,model,market):
      for blend in (.25,.5):candidates.add((variant,model,blend))
  settled=[r for r in completed if result(r,sport,market) is not None and candidate_vector(r,sport,market,base) is not None]
  bm=metrics(samples(settled,sport,market,base),labels)
  baseline_by_day={d:metrics(samples([r for r in settled if r['date']==d],sport,market,base),labels)
                   for d in sorted({r['date'] for r in settled})}
  ranked=[]
  for c in sorted(candidates):
   items=[(today_rule_vector(r,sport,market,c),result(r,sport,market)) for r in settled]
   m=metrics(items,labels)
   if m:
    fallback=sum(candidate_vector(r,sport,market,c) is None for r in settled)
    by_day={d:metrics([(today_rule_vector(r,sport,market,c),result(r,sport,market)) for r in settled if r['date']==d],labels)
            for d in baseline_by_day}
    ranked.append({'candidate':list(c),'metrics':m,'byDay':by_day,'fallbackCount':fallback,'changedInputCount':len(settled)-fallback})
  ranked.sort(key=lambda x:(x['metrics']['logLoss'],x['candidate']!=list(base),tuple(x['candidate'])))
  feasible=[x for x in ranked if bm and x['metrics']['accuracy']>=bm['accuracy']
            and (x['candidate']==list(base) or x['changedInputCount']>=max(10,math.ceil(.10*len(settled))))
            and all(x['byDay'][d]['accuracy']>=baseline_by_day[d]['accuracy'] for d in baseline_by_day)]
  rules['markets'][market]={'rule':feasible[0] if feasible else None,'baseline':bm,
                           'baselineByDay':baseline_by_day,'leaderboard':ranked,'minimumEstablishedEvidence':False,
                           'selectionTarget':'minimum cumulative log loss subject to no lower accuracy than the unchanged ensemble on every completed source day; no selection filtering'}
 score_candidates={('legacy',BASE[sport])}
 for r in completed:
  for variant,entry in r['variants'].items():
   for model in entry['models']:
    if score_value(r,sport,(variant,model)) is not None:score_candidates.add((variant,model))
   if sport=='football':score_candidates.add((variant,'PoissonExpectation'))
 baseline_score=score_rule_metrics(completed,sport,('legacy',BASE[sport]))
 score_baseline_by_day={d:score_rule_metrics([r for r in completed if r['date']==d],sport,('legacy',BASE[sport])) for d in sorted({r['date'] for r in completed})}
 ranked_scores=[]
 for c in sorted(score_candidates):
  m=score_rule_metrics(completed,sport,c)
  by_day={d:score_rule_metrics([r for r in completed if r['date']==d],sport,c) for d in score_baseline_by_day}
  if m and baseline_score and m['count']==baseline_score['count']:
   changed=sum(score_value(r,sport,c) is not None for r in completed)
   ranked_scores.append({'candidate':list(c),'metrics':m,'byDay':by_day,'changedInputCount':changed})
 ranked_scores.sort(key=lambda x:(x['metrics']['teamMAE'],x['candidate']!=['legacy',BASE[sport]],tuple(x['candidate'])))
 feasible_scores=[x for x in ranked_scores if x['metrics']['teamMAE']<=baseline_score['teamMAE']
                  and (x['candidate']==['legacy',BASE[sport]] or x['changedInputCount']>=max(10,math.ceil(.10*len(completed))))
                  and all(x['byDay'][d] and score_baseline_by_day[d] and x['byDay'][d]['teamMAE']<=score_baseline_by_day[d]['teamMAE'] for d in score_baseline_by_day)]
 rules['scores']={'rule':feasible_scores[0] if feasible_scores else None,'baseline':baseline_score,'baselineByDay':score_baseline_by_day,'leaderboard':ranked_scores,
                  'fallback':'unchanged legacy score if selected score candidate is unavailable','selectionTarget':'minimum cumulative team MAE with no worse team MAE on any completed source day'}
 return rules

def check_parity(rows,sport):
 maximum=0;bad=[]
 for r in rows:
  actual=r['variants']['legacy']['models'][BASE[sport]];expected=r['published']
  delta=max(abs(actual[k]-expected[k]) for k in ('pHome','pDraw','pAway','pOver25','pBttsYes'))
  maximum=max(maximum,delta)
  if delta>1e-8 or actual.get('scoreline')!=expected.get('scoreline'):bad.append({'date':r['date'],'eventId':r['eventId'],'delta':delta,'actualScore':actual.get('scoreline'),'publishedScore':expected.get('scoreline')})
 return {'maximumProbabilityDifference':maximum,'mismatchCount':len(bad),'mismatches':bad}

def evaluate(data):
 report={'markets':[],'models':[],'features':[],'scores':[],'parity':{},'recommendations':{},'invalidPredictions':[],'todayDerivedRules':{},
         'promotion':'disabled: insufficient independent days; no production change',
         'scope':'MS1/MSX/MS2, Alt/Üst, Var/Yok where supported. Handicap, period and player markets are not modeled.',
         'scoreTarget':'Saved production settlement score; football extra-time/penalty settlement may differ from a regulation forecast.'}
 for sport,rows in data.items():
  for r in rows:
   for variant,entry in r['variants'].items():
    for model in entry['models']:
     for market in GROUPS[sport]:
      if allowed(sport,model,market) and candidate_vector(r,sport,market,(variant,model,0)) is None:
       report['invalidPredictions'].append({'sport':sport,'date':r['date'],'eventId':r['eventId'],'role':r['role'],'variant':variant,'model':model,'market':market,'reason':'invalid or missing probability; excluded, never clamped'})
  report['parity'][sport]=check_parity(rows,sport)
  if report['parity'][sport]['mismatchCount']:raise ValueError('Baseline parity failed: '+json.dumps(report['parity'][sport]))
  train=[r for r in rows if r['role']=='training'];test=[r for r in rows if r['role']=='holdout']
  report['recommendations'][sport]={}
  for market,labels in GROUPS[sport].items():
   fitted=fit(train,sport,market);c=tuple(fitted['candidate']);baseline=('legacy',BASE[sport],0)
   hm=metrics(samples(test,sport,market,c),labels,fitted['threshold']);bm=metrics(samples(test,sport,market,baseline),labels)
   report['markets'].append({'sport':sport,'market':market,'training':fitted,'holdout':hm,'baselineHoldout':bm})
   report['recommendations'][sport][market]={'candidate':list(c),'threshold':fitted['threshold'],'provisional':True}
   models=sorted({m for r in rows for entry in r['variants'].values() for m in entry['models'] if allowed(sport,m,market)})
   for model in models:
    model_variant='six-balanced' if model.startswith('History') or model=='VarianceShrinkTotalsModel' else 'legacy'
    for role,subset in (('training',train),('holdout',test)):
     missing=sum(result(r,sport,market) is not None and candidate_vector(r,sport,market,(model_variant,model,0)) is None for r in subset)
     paired=[r for r in subset if candidate_vector(r,sport,market,(model_variant,model,0)) is not None and candidate_vector(r,sport,market,baseline) is not None]
     mm=metrics(samples(paired,sport,market,(model_variant,model,0)),labels)
     pm=metrics(samples(paired,sport,market,baseline),labels)
     report['models'].append({'sport':sport,'market':market,'model':model,'variant':model_variant,'role':role,'invalidSettledCount':missing,'metrics':mm,'pairedBaselineMetrics':pm,'deltaLogLoss':mm['logLoss']-pm['logLoss'] if mm and pm else None})
   for variant in sorted({v for r in rows for v in r['variants']}):
    if variant=='legacy':continue
    for role,subset in (('training',train),('holdout',test)):
     paired=[r for r in subset if variant in r['variants']]
     reference='wide-balanced' if variant.startswith('wide-no-') else 'six-balanced' if variant.startswith('six-no-') else 'legacy'
     paired=[r for r in paired if reference in r['variants']]
     paired=[r for r in paired if candidate_vector(r,sport,market,(variant,BASE[sport],0)) is not None and candidate_vector(r,sport,market,(reference,BASE[sport],0)) is not None]
     new=metrics(samples(paired,sport,market,(variant,BASE[sport],0)),labels)
     old=metrics(samples(paired,sport,market,(reference,BASE[sport],0)),labels)
     report['features'].append({'sport':sport,'market':market,'variant':variant,'reference':reference,'role':role,'metrics':new,'referenceMetrics':old,
                              'deltaLogLoss':new['logLoss']-old['logLoss'] if new and old else None})
  candidates={('legacy',BASE[sport])}
  for r in train:
   for v in ('legacy','six-balanced','six-simple','six-no-recency','six-no-venue','six-no-form'):
    if v not in r['variants']:continue
    for model in r['variants'][v]['models']:
     if score_value(r,sport,(v,model)) is not None:candidates.add((v,model))
    if sport=='football':candidates.add((v,'PoissonExpectation'))
  scored=[(score_metrics(train,sport,c),c) for c in sorted(candidates)]
  required=score_metrics(train,sport,('legacy',BASE[sport]))
  scored=[(m,c) for m,c in scored if m and required and m['count']==required['count'] and m['count']>=30]
  best=min(scored,key=lambda x:(x[0]['teamMAE'],x[1]))[1] if scored else ('legacy',BASE[sport])
  report['recommendations'][sport]['score']={'candidate':list(best),'provisional':True}
  for c in sorted(candidates):report['scores'].append({'sport':sport,'candidate':list(c),'training':score_metrics(train,sport,c),'holdout':score_metrics(test,sport,c),'chosenOnTraining':c==best})
  report['todayDerivedRules'][sport]=derive_today_rules(rows,sport)
 return report

STYLE="body{font-family:Segoe UI,Arial;background:#f3f6fa;color:#222;margin:0}main{max-width:1450px;padding:18px;margin:auto}h1{color:#004d80}nav{display:flex;gap:18px;flex-wrap:wrap}a{color:#0077cc}.box{background:white;border:1px solid #dce3ec;border-radius:10px;padding:16px;margin:16px 0}.scroll{overflow-x:auto}table{width:100%;border-collapse:collapse;background:white}th{background:#0077cc;color:white}td,th{padding:10px;text-align:center;border-bottom:1px solid #ddd}tr:nth-child(even){background:#f3f6fa}.note{padding:12px;background:#fff1df;border-radius:8px}summary{cursor:pointer;font-weight:bold}pre{white-space:pre-wrap;word-break:break-word}"
def pct(x):return '—' if x is None else f'%{100*x:.1f}'
def page(title,body):return "<!DOCTYPE html><html lang='tr'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>"+html.escape(title)+"</title><style>"+STYLE+"</style></head><body><main><h1>"+html.escape(title)+"</h1><nav><a href='index.html'>Günlük kıyas</a><a href='models.html'>Modeller</a><a href='features.html'>Geçmiş etkileri</a><a href='scores.html'>Skor tahminleri</a><a href='today-rules.html'>Bugünden çıkarılan kurallar</a><a href='day-by-day.html'>Gün gün takip</a><a href='errors.html'>Hata analizi</a></nav>"+body+"</main></body></html>"
def table(headers,rows):return "<div class='scroll'><table><tr>"+''.join('<th>'+html.escape(h)+'</th>' for h in headers)+"</tr>"+''.join('<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in row)+'</tr>' for row in rows)+"</table></div>"

def render(output,data,report):
 target=max(r['date'] for rows in data.values() for r in rows if r['role']=='holdout')
 note=f"<p class='note'>Önceki günler eğitim, {target} ayrı kontrol günüdür. Bugünün henüz tamamlanmayan sonuçları ölçüme girmez. Adaylar optimizasyonu kanıtlanmış model değildir; yayın ve Telegram değişmez. Bütün tahmin yönleri gösterilir; seçim eşiği ayrı değerlendirilir. Eski arşivlerde yıl bulunmayan tarihler sıra ve maç gününe göre çıkarılmıştır; ham tarih ve çıkarılan tarih sayısı JSON denetiminde bulunur, özellikle uzun aralarda belirsizlik vardır.</p>"
 body=note
 for sport,rows in data.items():
  for r in rows:
   if r['role']!='holdout':continue
   base=r['variants']['legacy']['models'][BASE[sport]]
   wide=r['variants'].get('wide-balanced',{}).get('models',{}).get(BASE[sport])
   body+="<article class='box'><h2>"+html.escape(r['name'])+" · "+html.escape(r['time'])+"</h2>"
   body+='<p>Gerçek skor: '+html.escape(str(r.get('realScore') or 'Bekliyor'))+' · Mevcut skor tahmini: '+html.escape(str(base.get('scoreline','—')))+' · Dengeli geniş geçmiş skoru: '+html.escape(str(wide.get('scoreline','—') if wide else 'Yeterli geniş geçmiş yok'))+'</p>'
   lines=[]
   for market,labels in GROUPS[sport].items():
    recommendation=report['recommendations'][sport][market];candidate=tuple(recommendation['candidate'])
    b=vector(base,sport,market);w=vector(wide,sport,market) if wide else None;p=candidate_vector(r,sport,market,candidate)
    today_rule=report['todayDerivedRules'][sport]['markets'][market]['rule']
    tp=today_rule_vector(r,sport,market,tuple(today_rule['candidate'])) if today_rule else None
    for i,label in enumerate(labels):lines.append((label,pct(b[i]),pct(w[i]) if w else '—',pct(p[i]) if p else '—',pct(tp[i]) if tp else '—'))
    pick=max(range(len(p)),key=lambda i:p[i]) if p else None
    body+='<p><strong>'+market+' aday yönü: '+(labels[pick] if pick is not None else 'Veri yok')+'</strong> · Eğitimde seçilen eşik: '+pct(recommendation['threshold'])+' · '+('Eşiği geçiyor' if p and max(p)>=recommendation['threshold'] else 'Eşiğin altında')+'</p>'
   body+=table(['Seçenek','Mevcut %','Dengeli geniş %','Önceki günlerde seçilen aday %','Bugünden çıkarılan kural % (eğitim)'],lines)
   score_candidate=tuple(report['recommendations'][sport]['score']['candidate']);sc=score_value(r,sport,score_candidate)
   if sc:body+=f'<p>Önceki günlerde seçilen skor adayı: {sc[0]:.2f}–{sc[1]:.2f} · '+html.escape(str(score_candidate))+'</p>'
   compact={v:{'models':entry['models'],'audit':{k:({kk:vv for kk,vv in value.items() if kk!='rows'} if isinstance(value,dict) else value) for k,value in entry.get('audit',{}).items()}} for v,entry in r['variants'].items()}
   body+="<details><summary>Her model ve veri sürümünün hesabı</summary><pre>"+html.escape(json.dumps(compact,ensure_ascii=False,indent=2))+"</pre></details></article>"
 (output/'index.html').write_text(page(target+' · Ensemble ve geçmiş kıyası',body),encoding='utf-8')
 body=note+"<p>Geçersiz olasılıklar düzeltilmiş gibi gösterilmez. Geçersiz sonuç sütunu modelin hesap üretemediği tamamlanmış maçları gösterir. Eğitim kapsamı eksik adaylar seçilemez. Eşleşen mevcut sistem ve log loss farkı yalnız aynı maçları karşılaştırır; negatif fark iyileşmedir.</p>"+table(['Spor','Pazar','Model','Veri','N','Geçersiz sonuç','İsabet','Eşleşen mevcut isabet','Brier','Log loss','Log loss farkı'],[(m['sport'],m['market'],m['model'],m['role'],m['metrics']['count'],m['invalidSettledCount'],pct(m['metrics']['accuracy']),pct(m['pairedBaselineMetrics']['accuracy']),f"{m['metrics']['brier']:.4f}",f"{m['metrics']['logLoss']:.4f}",f"{m['deltaLogLoss']:+.4f}") for m in report['models'] if m['metrics']])
 for m in report['markets']:
  hm=m['holdout'];bm=m['baselineHoldout'];body+="<section class='box'><h2>"+m['sport']+' '+m['market']+'</h2><p>Aday: '+html.escape(str(m['training']['candidate']))+'</p>'
  if hm and bm:body+=f"<p>Kontrol gününde mevcut isabet {pct(bm['accuracy'])}; aday {pct(hm['accuracy'])}. Eşikli aday: {hm['selectedCount']}/{hm['count']} maç; isabet {pct(hm['selectedAccuracy'])}.</p>"+table(['Seçenek','Seçilen N','İsabet','%95 aralık','Brier'],[(o['option'],o['predictedCount'],pct(o['precision']),str([round(v,3) for v in o['interval95']]) if o['interval95'] else '—',f"{o['brier']:.4f}") for o in hm['options']])
  body+='</section>'
 (output/'models.html').write_text(page('Alt modeller ve pazar bazında doğrulama',body),encoding='utf-8')
 body=note+"<p>Negatif log loss farkı bu eşleşen örneklerde iyileşme demektir. Bu bir neden-sonuç kanıtı değildir. Geniş geçmişin eski günlerdeki kapsamı yalnız 1 Ekim havuzuyla tam takım adı eşleşen takımlardır; N değerlerine dikkat edin.</p>"+table(['Spor','Pazar','Sürüm','Karşılaştırma','Veri','N','İsabet','Log loss farkı'],[(m['sport'],m['market'],m['variant'],m['reference'],m['role'],m['metrics']['count'],pct(m['metrics']['accuracy']),f"{m['deltaLogLoss']:+.4f}") for m in report['features'] if m['metrics']])
 (output/'features.html').write_text(page('Geçmiş, saha, güncellik ve form katkısı',body),encoding='utf-8')
 body=note+"<p>MAE ve RMSE düşük olduğunda skor tahmin hatası daha azdır. Ondalıklı beklenen skor ile tam skor isabeti farklı hedeflerdir; skor hiçbir pazar seçimini veto etmez.</p>"+table(['Spor','Skor hesabı','Veri','N','Takım MAE','Takım RMSE','Toplam hatası','Tam skor isabeti'],[(m['sport'],str(m['candidate']),role,m[role]['count'],f"{m[role]['teamMAE']:.3f}",f"{m[role]['teamRMSE']:.3f}",f"{m[role]['totalMAE']:.3f}",pct(m[role]['exactRoundedScoreRate'])) for m in report['scores'] for role in ('training','holdout') if m[role]])
 (output/'scores.html').write_text(page('Skor tahmini karşılaştırması',body),encoding='utf-8')
 body="<p class='note'>Bu sayfa bugünün sonuçlarından kural çıkarır. Buradaki başarı eğitim başarısıdır; aynı gün doğrulama sayılmaz. Kurallar yarın değişmeden sınanmak üzere frozen-today-rules.json dosyasına kaydedildi. Main ve Telegram değişmez.</p><p>Her pazar ayrı değerlendirilir. Tarih/saha/form ve geniş geçmiş sürümleri ile en az %50 mevcut ensemble bırakan alt model karışımları denenir. Tüm tamamlanmış maçlar aynı kohortta ölçülür; eksik geniş geçmişte mevcut sisteme dönüş önceden tanımlıdır. Bugünkü isabeti mevcut sistemin altına düşürmeyen adaylar arasından en düşük log loss seçilir; bu yarın isabetin düşmeyeceğini garanti etmez. Tablodaki liste olasılık hatasına göre sıralanır, düşük isabetli aday seçilemez. Skor için en düşük takım MAE adayı seçilir.</p>"
 for sport,rules in report['todayDerivedRules'].items():
  body+='<h2>'+sport+'</h2>'
  for market,entry in rules['markets'].items():
   if not entry['rule']:continue
   best=entry['rule'];base=entry['baseline'];m=best['metrics']
   body+='<section class="box"><h3>'+market+'</h3><p>Aday kural: '+html.escape(str(best['candidate']))+f" · N={m['count']} · eksik veriyle mevcut sisteme dönüş={best['fallbackCount']}</p><p>Bugünde mevcut isabet {pct(base['accuracy'])}, kural isabeti {pct(m['accuracy'])}; log loss {base['logLoss']:.4f} → {m['logLoss']:.4f}. Bu artış bağımsız test değildir.</p>"
   body+=table(['Veri sürümü / model / karışım','N','İsabet','Log loss','Mevcut sisteme dönüş'],[(str(x['candidate']),x['metrics']['count'],pct(x['metrics']['accuracy']),f"{x['metrics']['logLoss']:.4f}",x['fallbackCount']) for x in entry['leaderboard'][:10]])+'</section>'
  score=rules['scores']
  if score['rule']:body+='<p>Bugünden skor adayı: '+html.escape(str(score['rule']['candidate']))+f" · Takım MAE {score['baseline']['teamMAE']:.3f} → {score['rule']['metrics']['teamMAE']:.3f}</p>"
 body+='<h2>Bugünün geçmiş özelliği katkıları</h2><p>Çıkarıldığında log loss yükselen özellik, bu maçlarda yardımcı olmuş olabilir. Negatif fark çıkarılınca iyileşme demektir. Bir günlük ilişki kalıcı önem kanıtı değildir.</p>'+table(['Spor','Pazar','Çıkarılan özellik','N','Log loss farkı'],[(m['sport'],m['market'],m['variant'],m['metrics']['count'],f"{m['deltaLogLoss']:+.4f}") for m in report['features'] if m['role']=='holdout' and '-no-' in m['variant'] and m['metrics']])
 (output/'today-rules.html').write_text(page('Bugünün sonuçlarından yarın için aday kurallar',body),encoding='utf-8')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 data={s:json.loads((a.output/(s+'-replay.json')).read_text()) for s in GROUPS}
 report=evaluate(data);dump(a.output/'evaluation.json',report);render(a.output,data,report)
 holdout=max(r['date'] for rows in data.values() for r in rows if r['role']=='holdout')
 dump(a.output/'frozen-today-rules.json',{'derivedFromDate':holdout,'validFromDate':(date.fromisoformat(holdout)+timedelta(days=1)).isoformat(),'createdAt':datetime.now(timezone.utc).isoformat(),'purpose':'exploratory rule learned today; evaluate on future outcomes without refitting','rules':report['todayDerivedRules']})
 print(json.dumps({'parity':report['parity'],'promotion':report['promotion']},ensure_ascii=False))
