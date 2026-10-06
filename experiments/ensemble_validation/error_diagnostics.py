"""Describe correct/incorrect forecast cohorts; never fit or silently promote a rule."""
import argparse,json,statistics
from pathlib import Path
from prepare import dump
from report import GROUPS,BASE,result,candidate_vector,page,table

def diagnose(data):
 report=[]
 for sport,rows in data.items():
  for role in ('training','holdout'):
   for market in GROUPS[sport]:
    cohorts={True:[],False:[]};errors=[]
    for row in rows:
     if row['role']!=role:continue
     y=result(row,sport,market);p=candidate_vector(row,sport,market,('legacy',BASE[sport],0))
     f=row['variants'].get('six-balanced',{}).get('marketFeatureAudit')
     if y is None or p is None or not f:continue
     correct=max(range(len(p)),key=lambda i:p[i])==y
     h,a=f['home'],f['away']
     values={'meanScoringRate':(h['scoresRate']+a['scoresRate'])/2,
             'meanConcedingRate':(h['concedesRate']+a['concedesRate'])/2,
             'meanCleanSheetRate':(h['cleanSheetRate']+a['cleanSheetRate'])/2,
             'meanBlankRate':(h['blankRate']+a['blankRate'])/2,
             'meanHistoricalOverRate':(h['over25Rate']+a['over25Rate'])/2,
             'meanHistoricalBttsRate':(h['bttsRate']+a['bttsRate'])/2,
             'expectedTotal':(h['totalMean']+a['totalMean'])/2,
             'totalStdDev':((h['totalVariance']+a['totalVariance'])/2)**.5,
             'minimumHistoryCount':min(h['count'],a['count'])}
     if sport=='basketball':
      # Goal/2.5-goal event rates are not meaningful basketball predictors.
      for key in ('meanScoringRate','meanConcedingRate','meanCleanSheetRate','meanBlankRate','meanHistoricalOverRate','meanHistoricalBttsRate'):values.pop(key)
      values['expectedTotalMinusLine']=values['expectedTotal']-row['odds'].get('hOverUnderValue',0)
     cohorts[correct].append(values)
     if not correct:errors.append({'date':row['date'],'eventId':row['eventId'],'name':row['name'],'realScore':row['realScore'],'probabilities':p,'features':values})
    keys=sorted({k for items in cohorts.values() for f in items for k in f})
    report.append({'sport':sport,'role':role,'market':market,'correctCount':len(cohorts[True]),'errorCount':len(cohorts[False]),'features':[{'feature':k,'correctMean':statistics.mean(x[k] for x in cohorts[True]) if cohorts[True] else None,'errorMean':statistics.mean(x[k] for x in cohorts[False]) if cohorts[False] else None} for k in keys],'errors':errors})
 return report

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 data={s:json.loads((a.output/(s+'-replay.json')).read_text()) for s in BASE};r=diagnose(data)
 dump(a.output/'error-diagnostics.json',r)
 body='<p>Doğru ve yanlış tahminlerdeki geçmiş özelliklerinin ortalamaları. Bu bir ilişki teşhisidir; az örnekte fark rastlantısal olabilir. Tablodan yeni aday geliştirilebilir; bağımsız gün sonucu olmadan başarı kanıtı sayılmaz. Tüm hata maçları JSON dosyasında bulunur.</p>'
 body+=table(['Spor','Pazar','Veri','Doğru N','Yanlış N','Özellik','Doğru ortalama','Yanlış ortalama'],[(x['sport'],x['market'],x['role'],x['correctCount'],x['errorCount'],f['feature'],'—' if f['correctMean'] is None else f"{f['correctMean']:.3f}",'—' if f['errorMean'] is None else f"{f['errorMean']:.3f}") for x in r for f in x['features']])
 (a.output/'errors.html').write_text(page('Yanlış tahminlerde hangi veriler öne çıkıyor?',body),encoding='utf-8')
