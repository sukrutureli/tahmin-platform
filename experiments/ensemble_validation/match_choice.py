"""One saved best-probability market per fixture, followed by fixed top-half filtering."""
import argparse,hashlib,html,json,math
from datetime import datetime,timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from report import GROUPS,result,parse_score,wilson
from prepare import dump
from outcome_learning import score_metrics
from conditional_score import football_score,basketball_score,basket_covariance
from score_distribution import forecast

def choices(book,data,now=None):
    now=now or datetime.now(timezone.utc)
    inputs={(s,r['date'],str(r['eventId'])):r for s,rs in data.items() for r in rs}
    entries=[]
    for e in book['predictions']:
        if not e.get('prospectiveBeforeKickoff'):continue
        sport=e['sport'];r=inputs.get((sport,e['date'],str(e['eventId'])),{});options=[]
        for market,names in GROUPS[sport].items():
            p=e['markets'].get(market)
            if not p or len(p)!=len(names) or not all(isinstance(v,(int,float)) and math.isfinite(v) and 0<=v<=1 for v in p) or abs(sum(p)-1)>1e-6:continue
            line=2.5 if sport=='football' else r.get('odds',{}).get('hOverUnderValue',0)
            if market=='OU' and (not line or line<=0):continue
            i=max(range(len(p)),key=lambda i:p[i]);pick=names[i]
            if market=='OU':pick=f'{line:g} '+pick
            if market=='BTTS':pick='KG '+pick
            options.append((max(p),market,i,pick))
        if not options:continue
        # Stable market order resolves ties. No outcome, main prediction or score is used to select.
        confidence,market,index,pick=max(options,key=lambda v:v[0])
        try:before=now<datetime.fromisoformat(e['date']+'T'+r['time']).replace(tzinfo=ZoneInfo('Europe/Istanbul'))
        except (KeyError,TypeError,ValueError):before=False
        mean=e.get('scoreMeans',e.get('score'));score=None;independent=None;scored={}
        total_line=2.5 if sport=='football' else r.get('odds',{}).get('hOverUnderValue',0)
        if mean is not None and len(mean)==2 and all(math.isfinite(x) for x in mean):
            if sport=='football':
                model=e.get('scoreDistribution',{'dispersion':None,'rho':0})
                independent=forecast(mean,model)['score'];scored=football_score(mean,model,market,index,total_line)
            else:
                independent=[round(x) for x in mean];scored=basketball_score(mean,e.get('scoreCovariance',[[1.,0.],[0.,1.]]),market,index,total_line)
            score=scored['score']
        line=f'{score[0]}-{score[1]}' if score else None
        entries.append({'sport':sport,'date':e['date'],'eventId':str(e['eventId']),'name':e['name'],'time':r.get('time'),'market':market,'optionIndex':index,'pick':pick,'confidence':confidence,'score':score,'independentScore':independent,'scoreline':line,'scoreMethod':scored.get('method'),'scoreProbability':scored.get('probability'),'scoreConditionalProbability':scored.get('conditionalProbability'),'scoreConditionMass':scored.get('conditionMass'),'selectionBeforeKickoff':before,'selected':False})
    for sport in GROUPS:
        ranked=sorted([e for e in entries if e['sport']==sport],key=lambda e:(-e['confidence'],e['eventId']))
        for i,e in enumerate(ranked):e['rank']=i+1;e['selected']=i<math.ceil(len(ranked)/2)
    return {'targetDate':book['targetDate'],'createdAt':now.isoformat(),'forecastCreatedAt':book['createdAt'],'policy':'One max-probability market per match; top ceil(N/2) per sport; fixed policy independent of outcomes. Probabilities remain experimental.','predictions':entries}

def freeze(output,data,previous=None):
    source=output/'learned-before-results.json';digest=hashlib.sha256(source.read_bytes()).hexdigest();book=json.loads(source.read_text())
    old=previous/'match-choice-before-results.json' if previous else None
    if old and old.exists() and json.loads(old.read_text())['targetDate']==book['targetDate']:
        assert json.loads(old.read_text())['forecastSha256']==digest
        (output/'match-choice-before-results.json').write_bytes(old.read_bytes());return
    candidate=output/'score-before-results.json'
    if candidate.exists():
        scores=json.loads(candidate.read_text());assert scores['targetDate']==book['targetDate'] and scores['meanForecastSha256']==digest
        by_id={(e['sport'],e['date'],str(e['eventId'])):e for e in scores['predictions']}
        for e in book['predictions']:
            point=by_id.get((e['sport'],e['date'],str(e['eventId'])))
            if point:e['scoreMeans']=point.get('meanGoals',e['score']);e['scoreDistribution']=scores.get('model') or {'dispersion':None,'rho':0}
    context=output/'outcome-learning.json'
    covariance=basket_covariance(json.loads(context.read_text())) if context.exists() else [[1.,0.],[0.,1.]]
    for e in book['predictions']:
        if e['sport']=='basketball':e['scoreCovariance']=covariance
    saved=choices(book,data);saved['forecastSha256']=digest;dump(output/'match-choice-before-results.json',saved)

def settle(output,data,previous=None):
    saved=json.loads((output/'match-choice-before-results.json').read_text());source=output/'learned-before-results.json'
    assert saved['forecastSha256']==hashlib.sha256(source.read_bytes()).hexdigest()
    forecasts={(e['sport'],e['date'],str(e['eventId'])):e for e in json.loads(source.read_text())['predictions']}
    labels={(s,r['date'],str(r['eventId'])):r for s,rs in data.items() for r in rs}
    def evaluate(entries):
        samples=[];scores=[]
        for e in entries:
            key=(e['sport'],e['date'],e['eventId']);r=labels.get(key);y=result(r,e['sport'],e['market']) if r else None
            if y is None:continue
            f=forecasts[key];b=f['baselineMarkets'].get(e['market']);mainpick=max(range(len(b)),key=lambda i:b[i]) if b else None
            samples.append((e['confidence'],int(y==e['optionIndex']),mainpick==y if mainpick is not None else None))
            actual=parse_score({'scoreline':r.get('realScore')})
            if actual and e['score'] is not None and f['baselineScore'] is not None:scores.append((actual,e['score'],f['baselineScore'],e.get('independentScore')))
        if not samples:return None
        main=[h for p,y,h in samples if h is not None]
        mean_confidence=sum(p for p,y,h in samples)/len(samples)
        return {'count':len(samples),'hits':sum(y for p,y,h in samples),'accuracy':sum(y for p,y,h in samples)/len(samples),'accuracyInterval95':wilson(sum(y for p,y,h in samples),len(samples)),'meanConfidence':mean_confidence,'calibrationGap':sum(y for p,y,h in samples)/len(samples)-mean_confidence,
                'chosenEventBrier':sum((p-y)**2 for p,y,h in samples)/len(samples),'chosenEventLogLoss':-sum(y*math.log(max(p,1e-12))+(1-y)*math.log(max(1-p,1e-12)) for p,y,h in samples)/len(samples),
                'mainSameMarkets':{'count':len(main),'hits':sum(main),'accuracy':sum(main)/len(main)} if main else None,
                'scoreLearned':score_metrics([x[0] for x in scores],[x[1] for x in scores]),'scoreMain':score_metrics([x[0] for x in scores],[x[2] for x in scores]),
                'scoreIndependent':score_metrics([x[0] for x in scores if x[3] is not None],[x[3] for x in scores if x[3] is not None]),
                'scoreExactHits':sum(list(x[0])==x[1] for x in scores),'scoreIndependentExactHits':sum(list(x[0])==x[3] for x in scores if x[3] is not None)}
    report={'targetDate':saved['targetDate'],'selectionCreatedAt':saved['createdAt'],'policy':saved['policy'],'scorePolicy':'New scores condition on the saved market choice; independent scores remain separately measured. Old snapshots are unchanged.','sports':[]}
    for sport in GROUPS:
        es=[e for e in saved['predictions'] if e['sport']==sport];sel=[e for e in es if e['selected']]
        subsets=[]
        for fraction in [.25,.5,.75,1.]:
            limit=math.ceil(len(es)*fraction);group=[e for e in es if e['rank']<=limit]
            subsets.append({'topFraction':fraction,'plannedCount':len(group),'minimumConfidence':min((e['confidence'] for e in group),default=None),'exploratory':evaluate(group),'prospective':evaluate([e for e in group if e['selectionBeforeKickoff']])})
        report['sports'].append({'sport':sport,'forecastCount':len(es),'selectedCount':len(sel),'all':evaluate(es),'selectedExploratory':evaluate(sel),'selectedProspective':evaluate([e for e in sel if e['selectionBeforeKickoff']]),'confidenceSubsets':subsets})
    dump(output/'match-choice-evaluation.json',report)
    old=previous/'match-choice-journal.json' if previous else None
    journal=json.loads(old.read_text()) if old and old.exists() else []
    journal=[x for x in journal if x['targetDate']!=report['targetDate']]+[report];dump(output/'match-choice-journal.json',sorted(journal,key=lambda x:x['targetDate']))
    def stats(m):return 'Henüz sonuç yok' if m is None else f"{m['hits']}/{m['count']} (%{100*m['accuracy']:.1f})"
    summary=''.join('<p>'+s['sport']+' · tüm tek tercihler: '+stats(s['all'])+' · seçilen yarı: '+stats(s['selectedExploratory'])+' · maç öncesinden seçilen yarı: '+stats(s['selectedProspective'])+'</p>' for s in report['sports'])
    subset_rows=''
    for s in report['sports']:
        for g in s['confidenceSubsets']:
            m=g['exploratory'];values=[s['sport'],f"İlk %{100*g['topFraction']:.0f}",g['plannedCount'],stats(m),f"%{100*m['meanConfidence']:.1f}" if m else '—',f"{m['chosenEventBrier']:.3f}" if m else '—',f"{m['chosenEventLogLoss']:.3f}" if m else '—',f"{m['scoreLearned']['teamMAE']:.3f}" if m and m['scoreLearned'] else '—',stats(g['prospective'])]
            subset_rows+='<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in values)+'</tr>'
    subset_table='<h2>Güven sırasına göre alt kümeler</h2><p>İlk %25/%50/%75 grupları birbirini içerir; bağımsız örneklemler değildir. Sıralama sonuçlar görülmeden kaydedilir. İsabet ve ortalama güven yalnız sonucu tamamlanan aynı örneklerde ölçülür. Maç öncesinden belirlenen alt küme ayrı gösterilir; geç seçimler araştırmadır. Brier burada seçilen tercihin ikili gerçekleşme hatasıdır. MAE takım başına gol/sayı hatasıdır. Küçük gruplarda yüksek yüzde tek başına kanıt değildir.</p><section><table><thead><tr><th>Spor</th><th>Alt küme</th><th>Planlanan maç</th><th>Sonuçlanan: isabet</th><th>Ortalama güven</th><th>Brier</th><th>Log loss</th><th>Skor MAE</th><th>Maç öncesi seçilen: isabet</th></tr></thead><tbody>'+subset_rows+'</tbody></table></section>'
    ordered=sorted(saved['predictions'],key=lambda x:(x['time'] or '99:99',x['eventId']))
    rows=''
    for e in ordered:
        r=labels.get((e['sport'],e['date'],e['eventId']));actual=parse_score({'scoreline':r.get('realScore')}) if r else None;y=result(r,e['sport'],e['market']) if r else None
        status=('✅' if y==e['optionIndex'] else '❌') if y is not None else ('İade / doğrulanmadı' if actual else 'Bekleniyor')
        values=[e['time'] or '—','Futbol' if e['sport']=='football' else 'Basketbol',e['name'],e['pick'],e['scoreline'] or '—',f"%{100*e['confidence']:.1f}",f"%{100*e['scoreProbability']:.1f}" if e.get('scoreProbability') is not None else '—',f'{int(actual[0])}-{int(actual[1])}' if actual else '—',status,'İlk %50' if e['selected'] else 'Diğer yarı','maç öncesi' if e['selectionBeforeKickoff'] else 'geç seçim / araştırma']
        rows+='<tr data-confidence="'+str(e['confidence'])+'" data-time="'+html.escape(e['time'] or '99:99',quote=True)+'">'+''.join('<td>'+html.escape(str(x))+'</td>' for x in values)+'</tr>'
    controls='<nav aria-label="Maç sıralaması"><button type="button" id="sort-time" aria-pressed="true">Saate göre sırala</button> <button type="button" id="sort-confidence" aria-pressed="false">Güvene göre sırala ↓</button><span id="sort-status" aria-live="polite"> Saat: erkenden geçe</span></nav>'
    script='''<script>
    const body=document.getElementById('matches');
    function order(mode){
      const rows=Array.from(body.rows);
      rows.sort((a,b)=>mode==='confidence' ? Number(b.dataset.confidence)-Number(a.dataset.confidence)||a.dataset.time.localeCompare(b.dataset.time) : a.dataset.time.localeCompare(b.dataset.time)||Number(b.dataset.confidence)-Number(a.dataset.confidence));
      rows.forEach(row=>body.appendChild(row));
      document.getElementById('sort-time').setAttribute('aria-pressed',String(mode==='time'));
      document.getElementById('sort-confidence').setAttribute('aria-pressed',String(mode==='confidence'));
      document.getElementById('sort-status').textContent=mode==='confidence'?' Güven: yüksekten düşüğe':' Saat: erkenden geçe';
    }
    document.getElementById('sort-time').addEventListener('click',()=>order('time'));
    document.getElementById('sort-confidence').addEventListener('click',()=>order('confidence'));
    </script>'''
    (output/'best-matches.html').write_text('<!doctype html><html lang="tr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Tek tercih ve skor</title><style>body{font:16px/1.6 system-ui;max-width:1150px;margin:24px auto;padding:18px;color:#19304a}table{border-collapse:collapse;width:100%}td,th{padding:10px;border-bottom:1px solid #dde3ee;text-align:left}section{overflow:auto}td{white-space:nowrap}nav{margin:20px 0}button{padding:12px 16px;border:1px solid #b5c5d9;border-radius:8px;background:#fff;color:#19304a;font:inherit;cursor:pointer}button[aria-pressed=true]{background:#19304a;color:#fff}#sort-status{display:inline-block;margin:8px}</style><h1>Tek tercih ve skor · '+saved['targetDate']+'</h1><p>Tüm maçlar listelenir. Her maç için MS/Alt-Üst/Var-Yok seçeneklerinden modelin en yüksek olasılıklı tek tercihi. Güven yüzdesi model tahminidir; başarı garantisi değildir. Yeni kayıtlarda skor seçilen tercihle uyumlu adaylar arasından hesaplanır; eski kayıtlar değiştirilmez. Tam skor olasılığı ve tercih güveni farklı değerlerdir. Geç oluşturulan seçimler ileriye dönük başarı sayılmaz. Eksik/canlı sonuçlar istatistiklere alınmaz.</p>'+summary+controls+'<section><table><thead><tr><th>Saat</th><th>Spor</th><th>Maç</th><th>Tek tercih</th><th>Skor tahmini</th><th>Tercih güveni</th><th>Tam skor olasılığı</th><th>Gerçek skor</th><th>Tercih sonucu</th><th>Güven grubu</th><th>Kayıt</th></tr></thead><tbody id="matches">'+rows+'</tbody></table></section>'+subset_table+script+'</html>')

def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['freeze','settle']);p.add_argument('--output',type=Path,required=True);p.add_argument('--previous',type=Path);a=p.parse_args()
    data={s:json.loads((a.output/(s+'-replay.json')).read_text()) for s in GROUPS};(freeze if a.mode=='freeze' else settle)(a.output,data,a.previous)
if __name__=='__main__':main()
