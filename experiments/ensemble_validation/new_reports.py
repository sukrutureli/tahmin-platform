"""Two presentation-only reports for the locked shadow model; never fit or rewrite forecasts."""
import argparse,hashlib,html,json,math,re
from pathlib import Path
from responsive_report import STYLE,SCRIPT
from display_odds import display_values
from report import GROUPS,result,parse_score

def read(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def reports(root):
    root=Path(root);locked=root/'stability-before-results.json';preview=not locked.exists()
    source=locked if locked.exists() else root/'context-before-results.json'
    book=read(source);target=book['targetDate']
    if preview and target!='2026-10-18':raise ValueError('Missing locked forecast snapshot; cannot silently switch models')
    model=root/'stability-model.json'
    if not model.exists():raise ValueError('Missing frozen model')
    model_hash=sha(model)
    if not preview and book['modelSha256']!=model_hash:raise ValueError('Frozen model hash mismatch')
    before={p.name:sha(p) for p in root.glob('*before-results*.json')};before[model.name]=model_hash
    config=read(model)['protocol'];payload=read(model)['payload'];summary={}
    for sport,folder,title in [('football','futbol','⚽ Futbol Yeni'),('basketball','basketbol','🏀 Basketbol Yeni')]:
        labels={(r['date'],str(r['eventId'])):r for r in read(root/(sport+'-replay.json'))}
        entries=book['systems'][sport]['opponent' if preview else book['version']]
        es=[]
        for e in entries:
            row=labels.get((target,str(e['eventId'])))
            if row is None:raise ValueError('Fixture missing in saved replay')
            c=e.get('chosen')
            if preview:
                choices=[]
                for m,names in GROUPS[sport].items():
                    if sport=='basketball' and m=='OU' and row.get('odds',{}).get('hOverUnderValue',0)<=0:continue
                    p=e['markets'][m];i=max(range(len(p)),key=lambda i:p[i]);choices.append((p[i],m,i))
                p,m,i=max(choices,key=lambda x:x[0]);c={'confidence':p,'market':m,'option':i}
            if not c:raise ValueError('Missing saved maximum market')
            score=e.get('score')
            line=2.5 if sport=='football' else row.get('odds',{}).get('hOverUnderValue',0)
            if preview:
                from conditional_score import football_score,basketball_score
                score=(football_score(e['scoreMean'],payload['footballDistribution'],c['market'],c['option'],line) if sport=='football' else basketball_score(e['scoreMean'],payload['basketballCovariance'],c['market'],c['option'],line))['score']
            es.append((e,row,c,score,line))
        es.sort(key=lambda x:(-x[2]['confidence'],str(x[0]['eventId'])))
        eligible=[x for x in es if x[0].get('prospectiveBeforeKickoff',False)]
        positions={str(x[0]['eventId']):i for i,x in enumerate(eligible)}
        rows=[];hits=finished=0
        for rank,(e,row,c,score,line) in enumerate(es):
            p=c['confidence'];m=c['market'];i=c['option'];label=GROUPS[sport][m][i]
            label=('KG '+label) if m=='BTTS' else (f'{line:g} '+label) if m=='OU' else label
            price,mbs=display_values(dict(row,sport=sport),m,i)
            name=html.escape(e['name'])+f'<span class="bet-meta">Oran <b>{price}</b> · MBS <b>{mbs}</b></span>'
            actual=parse_score({'scoreline':row.get('realScore')});y=result(row,sport,m)
            status=('✅ Kazandı' if y==i else '❌ Kaybetti') if y is not None else ('İade / doğrulanmadı' if actual else 'Bekleniyor')
            if y is not None:finished+=1;hits+=int(y==i)
            late=not e.get('prospectiveBeforeKickoff',False)
            position=positions.get(str(e['eventId']),0)
            tier='tier-late' if late else 'tier-25' if position<math.ceil(len(eligible)*.25) else 'tier-50' if position<math.ceil(len(eligible)*.5) else 'tier-75' if position<math.ceil(len(eligible)*.75) else 'tier-rest'
            vals=[e.get('time') or '—',title,name,label,'-'.join(str(int(x)) for x in score) if score else '—',f'%{100*p:.1f}','—','-'.join(str(int(x)) for x in actual) if actual else '—',status,'Geç kayıt' if late else 'Maç öncesi','']
            heads=['Saat','Spor','Maç','Tek tercih','Skor tahmini','Güven','Tam skor olasılığı','Gerçek skor','Sonuç','Kayıt','']
            cells=''.join('<td data-label="'+html.escape(h)+'">'+(str(v) if j==2 else html.escape(str(v)))+'</td>' for j,(h,v) in enumerate(zip(heads,vals)))
            rows.append(f'<tr class="{tier}" data-event-id="{html.escape(str(e["eventId"]))}" data-confidence="{p}" data-time="{html.escape(e.get("time") or "99:99")}">{cells}</tr>')
        state='Başlangıç günü · 14 günlük bağımsız ölçüme dahil değil.' if preview else 'Sabit model · bağımsız izleme · ana kıyas ilk %50.'
        provenance=read(root/'control-provenance.json') if (root/'control-provenance.json').exists() else {}
        updated=provenance.get('completedAt') or book.get('createdAt','')
        body=f'<h1>{title} · {target}</h1><p>{html.escape(state)} Her maçta tek tercih ve tercihle uyumlu skor.</p><p>{len(es)} maç · sonuçlanan tercihler {finished} · doğru {hits}. Son kontrol: {html.escape(updated)}</p>'
        body+='<nav><button id="sort-time" type="button" aria-pressed="false">Saate göre</button><button id="sort-confidence" type="button" aria-pressed="true">Güvene göre ↓</button><span id="sort-status">Güven: yüksekten düşüğe</span></nav>'
        body+='<div class="legend"><span class="tier-25">İlk %25</span><span class="tier-50">Sonraki %25</span><span class="tier-75">Üçüncü %25</span><span>Son %25</span></div>'
        body+=f'<section id="{sport}"><table class="match-table"><tbody class="match-list" id="matches-{sport}">'+''.join(rows)+'</tbody></table></section>'
        body+='<details><summary>Bilgi</summary><p>Güven, model olasılığıdır; gerçekleşmiş isabet garantisi değildir. Oranlar ilk kayıttandır, canlı değildir. Eksik oran/MBS “—” gösterilir. Sonuçlar yalnız tamamlanmış HTTP kayıtlarından gelir; canlı/eksik sonuçlar başarı paydasına girmez. Renkler güven sırasını gösterir. Kontrol tahminleri ve modeli değiştirmez.</p></details>'
        css=STYLE+'.bet-meta{display:block;font:500 12px/1.5 system-ui;color:#64788c;margin-top:7px}.bet-meta b{font-size:13px;color:#173d57}.match-list td:nth-child(7){display:none}'
        doc='<!doctype html><html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+title+' · '+target+'</title><style>'+css+'</style></head><body><main>'+body+'</main>'+SCRIPT+'</body></html>'
        name=folder+'-yeni.html';(root/name).write_text(doc)
        summary[folder]={'file':name,'sha256':sha(root/name),'fixtureCount':len(es),'settledChoiceCount':finished,'hits':hits}
    for name,digest in before.items():
        if sha(root/name)!=digest:raise ValueError('Presentation changed frozen forecast/model')
    manifest={'targetDate':target,'version':config['version'],'modelSha256':model_hash,'snapshotSha256':sha(source),'snapshotFile':source.name,'snapshotCreatedAt':book.get('createdAt'),'previewOnly':preview,'firstIndependentDate':config['first_forecast_date'],'updatedAt':updated,'reports':summary}
    (root/'new-report-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    return manifest

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();reports(a.output)
