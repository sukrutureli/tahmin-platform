"""Fixed top-half confidence selection; immutable and separately timed from forecasts."""
import argparse, hashlib, html, json, math
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from prepare import dump
from report import GROUPS, metrics, result, parse_score
from outcome_learning import score_metrics

def select(book, rows, now=None):
    now=now or datetime.now(timezone.utc)
    times={(s,r['date'],str(r['eventId'])):r.get('time') for s,rs in rows.items() for r in rs}
    out={'targetDate':book['targetDate'],'createdAt':now.isoformat(),'policy':'Fixed top 50% per sport/market; rank by saved max probability, eventId breaks ties; no outcome-dependent threshold.',
         'forecastCreatedAt':book['createdAt'],'groups':[]}
    for sport,markets in GROUPS.items():
        for market in markets:
            eligible=[]
            for e in book['predictions']:
                p=e.get('markets',{}).get(market)
                if e['sport']!=sport or not e.get('prospectiveBeforeKickoff') or not p:continue
                if len(p)!=len(markets[market]) or not all(isinstance(v,(int,float)) and math.isfinite(v) and 0<=v<=1 for v in p) or abs(sum(p)-1)>1e-6:continue
                eligible.append(e)
            ranked=sorted(eligible,key=lambda e:(-max(e['markets'][market]),str(e['eventId'])))
            selected=ranked[:math.ceil(len(ranked)/2)]
            entries=[]
            for e in selected:
                try:before=now<datetime.fromisoformat(e['date']+'T'+times[(sport,e['date'],str(e['eventId']))]).replace(tzinfo=ZoneInfo('Europe/Istanbul'))
                except (KeyError,TypeError,ValueError):before=False
                p=e['markets'][market];i=max(range(len(p)),key=lambda i:p[i])
                entries.append({'eventId':str(e['eventId']),'name':e['name'],'pick':markets[market][i],'confidence':max(p),'selectionBeforeKickoff':before})
            out['groups'].append({'sport':sport,'market':market,'eligibleCount':len(eligible),'selectedCount':len(entries),'cutoff':max(selected[-1]['markets'][market]) if selected else None,'entries':entries})
    return out

def freeze(output, data, previous=None):
    source=output/'learned-before-results.json';book=json.loads(source.read_text())
    old=previous/'selection-before-results.json' if previous else None
    if old and old.exists() and json.loads(old.read_text()).get('targetDate')==book['targetDate']:
        saved=json.loads(old.read_text());assert saved['forecastSha256']==hashlib.sha256(source.read_bytes()).hexdigest(), 'Forecast changed under saved selection'
        (output/'selection-before-results.json').write_bytes(old.read_bytes());return
    out=select(book,data);out['forecastSha256']=hashlib.sha256(source.read_bytes()).hexdigest()
    dump(output/'selection-before-results.json',out)

def settle(output,data,previous=None):
    saved=json.loads((output/'selection-before-results.json').read_text());source=output/'learned-before-results.json'
    assert hashlib.sha256(source.read_bytes()).hexdigest()==saved['forecastSha256']
    book=json.loads(source.read_text());labels={(s,r['date'],str(r['eventId'])):r for s,rs in data.items() for r in rs}
    report={'targetDate':saved['targetDate'],'selectionCreatedAt':saved['createdAt'],'status':'Late selections are exploratory even when the original forecasts were before kickoff. Missing/live results excluded.','groups':[]}
    for g in saved['groups']:
        sport,market=g['sport'],g['market'];chosen={e['eventId']:e for e in g['entries']};full=[];selected=[];prospective=[]
        for e in book['predictions']:
            if e['sport']!=sport or not e.get('prospectiveBeforeKickoff'):continue
            r=labels.get((sport,e['date'],str(e['eventId'])));y=result(r,sport,market) if r else None
            p=e['markets'].get(market);b=e['baselineMarkets'].get(market)
            if y is None or not p or not b:continue
            item=(e,p,b,y,r);full.append(item)
            if str(e['eventId']) in chosen:
                selected.append(item)
                if chosen[str(e['eventId'])]['selectionBeforeKickoff']:prospective.append(item)
        out={k:g[k] for k in ('sport','market','eligibleCount','selectedCount','cutoff')}
        for name,items in [('allForecasts',full),('selectedExploratory',selected),('selectedProspective',prospective)]:
            scored=[(e,parse_score({'scoreline':r['realScore']})) for e,p,b,y,r in items if e.get('score') is not None and e.get('baselineScore') is not None]
            out[name]={'learned':metrics([(p,y) for e,p,b,y,r in items],GROUPS[sport][market]),'mainSameCohort':metrics([(b,y) for e,p,b,y,r in items],GROUPS[sport][market]),
                       'scoreLearned':score_metrics([a for e,a in scored],[e['score'] for e,a in scored]),'scoreMain':score_metrics([a for e,a in scored],[e['baselineScore'] for e,a in scored])}
        report['groups'].append(out)
    dump(output/'selection-evaluation.json',report)
    journal=[];old=previous/'selection-journal.json' if previous else None
    if old and old.exists():journal=json.loads(old.read_text())
    journal=[x for x in journal if x['targetDate']!=report['targetDate']]+[report]
    dump(output/'selection-journal.json',sorted(journal,key=lambda x:x['targetDate']))
    def cell(m):return '—' if not m else f"{round(m['accuracy']*m['count'])}/{m['count']} ({100*m['accuracy']:.1f}%)"
    rows=''.join('<tr>'+''.join('<td>'+html.escape(str(x))+'</td>' for x in [g['sport']+' '+g['market'],g['selectedCount'],cell(g['allForecasts']['learned']),cell(g['selectedExploratory']['learned']),cell(g['selectedExploratory']['mainSameCohort']),cell(g['selectedProspective']['learned'])])+'</tr>' for g in report['groups'])
    picks=''.join('<h2>'+html.escape(g['sport']+' '+g['market'])+'</h2><ul>'+''.join('<li>'+html.escape(e['name']+' · '+e['pick'])+f" · %{100*e['confidence']:.1f}"+(' · maç öncesi seçim' if e['selectionBeforeKickoff'] else ' · geç seçim, araştırma')+'</li>' for e in g['entries'])+'</ul>' for g in saved['groups'])
    (output/'selection.html').write_text('<!doctype html><html lang="tr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>En güvenli yarı</title><style>body{font:16px/1.6 system-ui;max-width:1100px;margin:30px auto;padding:20px;color:#19304a}table{border-collapse:collapse}td,th{padding:10px;border-bottom:1px solid #ddd}section{overflow:auto}</style><h1>En güvenli yarı · '+saved['targetDate']+'</h1><p>Her spor/pazarda maç öncesi kaydedilmiş olasılığa göre ilk %50. Seçim oranı sabit; sonuçlara göre ayarlanmaz. Bu seçim tüm pazarlarda isabet artışını garanti etmez. Geç oluşturulan seçimler araştırmadır; ileriye dönük başarı olarak sayılmaz. Eksik/canlı sonuçlar değerlendirmeye alınmaz. Skor tahminleri korunur.</p><section><table><tr><th>Pazar</th><th>Seçilen</th><th>Tüm tahminler</th><th>Seçilenler (araştırma dahil)</th><th>Main aynı seçilen maçlar</th><th>Maç öncesi seçilenler</th></tr>'+rows+'</table></section>'+picks+'</html>')

def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['freeze','settle']);p.add_argument('--output',type=Path,required=True);p.add_argument('--previous',type=Path);a=p.parse_args()
    data={s:json.loads((a.output/(s+'-replay.json')).read_text()) for s in GROUPS}
    (freeze if a.mode=='freeze' else settle)(a.output,data,a.previous)
if __name__=='__main__':main()
