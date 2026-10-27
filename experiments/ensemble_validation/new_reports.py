"""Two presentation-only reports for the locked shadow model; never fit or rewrite forecasts."""
import argparse,hashlib,html,json,math,re
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from responsive_report import STYLE,SCRIPT
from display_odds import display_values
from report import GROUPS,result,parse_score
from priced_choices import freeze as priced_freeze,settle as priced_settle

LEGACY_FILTER_SCRIPT="<script>\n(()=>{const input=document.getElementById('min-odds'),search=document.getElementById('match-search'),mbs=document.getElementById('mbs-filter'),pick=document.getElementById('pick-filter'),finished=document.getElementById('hide-finished'),started=document.getElementById('hide-started'),rows=[...document.querySelectorAll('.match-list tr')],count=document.getElementById('filter-count');\nfunction normalize(value){return value.replace(/ı/g,'i').normalize('NFD').replace(/[\\u0300-\\u036f]/g,'').toLowerCase();}\nfor(const value of [...new Set(rows.map(row=>row.dataset.pick).filter(Boolean))].sort((a,b)=>a.localeCompare(b,'tr'))){const option=document.createElement('option');option.value=value;option.textContent=value;pick.appendChild(option);}\nfunction filter(){const terms=normalize(search.value).trim().split(/\\s+/).filter(Boolean);const raw=input.value.trim(),min=raw===''?null:Number(raw.replace(',','.')),now=Date.now();let n=0;for(const row of rows){const odd=Number(row.dataset.odds),kickoff=Date.parse(row.dataset.kickoff||'');const below=min!==null&&Number.isFinite(min)&&!(odd>1&&odd>=min),wrongMbs=mbs.value!==''&&row.dataset.mbs!==mbs.value,wrongPick=pick.value!==''&&row.dataset.pick!==pick.value,done=finished.checked&&row.dataset.finished==='1',begun=started.checked&&Number.isFinite(kickoff)&&kickoff<=now;row.hidden=below||wrongMbs||wrongPick||done||begun||!terms.every(term=>normalize(row.dataset.search||'').includes(term));if(!row.hidden)n++;}count.textContent=n+' / '+rows.length+' maç';}\ninput.addEventListener('input',filter);search.addEventListener('input',filter);mbs.addEventListener('change',filter);pick.addEventListener('change',filter);finished.addEventListener('change',filter);started.addEventListener('change',filter);document.getElementById('clear-odds').addEventListener('click',()=>{input.value='';search.value='';mbs.value='';pick.value='';finished.checked=false;started.checked=false;filter();});setInterval(filter,30000);window.addEventListener('focus',filter);filter();})();\n</script>"

FILTER_SCRIPT="<script>\n(()=>{const input=document.getElementById('min-odds'),search=document.getElementById('match-search'),mbs=document.getElementById('mbs-filter'),pick=document.getElementById('pick-filter'),finished=document.getElementById('hide-finished'),started=document.getElementById('hide-started'),rows=[...document.querySelectorAll('.match-list tr')],count=document.getElementById('filter-count');\nfunction normalize(value){return value.replace(/ı/g,'i').normalize('NFD').replace(/[\\u0300-\\u036f]/g,'').toLowerCase();}\nfor(const value of [...new Set(rows.map(row=>row.dataset.pick).filter(Boolean))].sort((a,b)=>a.localeCompare(b,'tr'))){const label=document.createElement('label'),box=document.createElement('input');box.type='checkbox';box.value=value;label.appendChild(box);label.appendChild(document.createTextNode(value));pick.appendChild(label);}\nfunction selected(group){return [...group.querySelectorAll('input:checked')].map(box=>box.value);}\nfunction filter(){const terms=normalize(search.value).trim().split(/\\s+/).filter(Boolean),mbsValues=selected(mbs),pickValues=selected(pick);const raw=input.value.trim(),min=raw===''?null:Number(raw.replace(',','.')),now=Date.now();let n=0;for(const row of rows){const odd=Number(row.dataset.odds),kickoff=Date.parse(row.dataset.kickoff||'');const below=min!==null&&Number.isFinite(min)&&!(odd>1&&odd>=min),wrongMbs=mbsValues.length>0&&!mbsValues.includes(row.dataset.mbs),wrongPick=pickValues.length>0&&!pickValues.includes(row.dataset.pick),done=finished.checked&&row.dataset.finished==='1',begun=started.checked&&Number.isFinite(kickoff)&&kickoff<=now;row.hidden=below||wrongMbs||wrongPick||done||begun||!terms.every(term=>normalize(row.dataset.search||'').includes(term));if(!row.hidden)n++;}count.textContent=n+' / '+rows.length+' maç';}\ninput.addEventListener('input',filter);search.addEventListener('input',filter);mbs.addEventListener('change',filter);pick.addEventListener('change',filter);finished.addEventListener('change',filter);started.addEventListener('change',filter);document.getElementById('clear-odds').addEventListener('click',()=>{input.value='';search.value='';for(const group of [mbs,pick])for(const box of group.querySelectorAll('input'))box.checked=false;finished.checked=false;started.checked=false;filter();});setInterval(filter,30000);window.addEventListener('focus',filter);filter();})();\n</script>"


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
    if preview and sha(source)!=read(model)['sourceSnapshotSha256']:raise ValueError('Source-day snapshot differs from the locked model source')
    if not preview and book['modelSha256']!=model_hash:raise ValueError('Frozen model hash mismatch')
    before={p.name:sha(p) for p in root.glob('*before-results*.json')};before[model.name]=model_hash
    config=read(model)['protocol'];payload=read(model)['payload'];summary={}
    priced=priced_freeze(root);priced_settle(root)
    for sport,folder,title in [('football','futbol','⚽ Futbol Yeni'),('basketball','basketbol','🏀 Basketbol Yeni')]:
        labels={(r['date'],str(r['eventId'])):r for r in read(root/(sport+'-replay.json'))}
        entries=priced['systems'][sport]['experiment']
        es=[]
        for e in entries:
            row=labels.get((target,str(e['eventId'])))
            if row is None:raise ValueError('Fixture missing in saved replay')
            c=e.get('chosen');score=e.get('score')
            line=2.5 if sport=='football' else (row.get('odds') or {}).get('hOverUnderValue',0)
            es.append((e,row,c,score,line))
        es.sort(key=lambda x:(-(x[2]['confidence'] if x[2] else -1),str(x[0]['eventId'])))
        eligible=[x for x in es if x[2] and x[0].get('prospectiveBeforeKickoff',False)]
        positions={str(x[0]['eventId']):i for i,x in enumerate(eligible)}
        rows=[];hits=finished=0
        for rank,(e,row,c,score,line) in enumerate(es):
            p=c['confidence'] if c else 0;m=c['market'] if c else None;i=c['option'] if c else None
            base_label=GROUPS[sport][m][i] if c else ''
            pick_filter=('KG '+base_label) if m=='BTTS' else base_label
            label=('KG '+base_label) if m=='BTTS' else (f'{line:g} '+base_label) if m=='OU' else (base_label or 'Oranlı tercih yok')
            price,mbs=display_values(dict(row,sport=sport),m,i)
            if c:price=f"{c['price']:.2f}"
            name=html.escape(e['name'])+f'<span class="bet-meta">Oran <b>{price}</b> · MBS <b>{mbs}</b></span>'
            actual=parse_score({'scoreline':row.get('realScore')});y=result(row,sport,m) if c else None
            status=(('✅ Kazandı' if y==i else '❌ Kaybetti') if y is not None else ('İade / doğrulanmadı' if actual else 'Bekleniyor')) if c else 'Tercih yok'
            if y is not None:finished+=1;hits+=int(y==i)
            late=not e.get('prospectiveBeforeKickoff',False)
            position=positions.get(str(e['eventId']),0)
            tier='tier-late' if late else 'tier-25' if position<math.ceil(len(eligible)*.25) else 'tier-50' if position<math.ceil(len(eligible)*.5) else 'tier-75' if position<math.ceil(len(eligible)*.75) else 'tier-rest'
            vals=[e.get('time') or '—',title,name,label,'-'.join(str(int(x)) for x in score) if score else '—',f'%{100*p:.1f}' if c else '—','—','-'.join(str(int(x)) for x in actual) if actual else '—',status,'Geç kayıt' if late else 'Maç öncesi','']
            heads=['Saat','Spor','Maç','Tek tercih','Skor tahmini','Güven','Tam skor olasılığı','Gerçek skor','Sonuç','Kayıt','']
            cells=''.join('<td data-label="'+html.escape(h)+'">'+(str(v) if j==2 else html.escape(str(v)))+'</td>' for j,(h,v) in enumerate(zip(heads,vals)))
            try:kickoff=datetime.fromisoformat(target+'T'+e['time']).replace(tzinfo=ZoneInfo('Europe/Istanbul')).isoformat()
            except (ValueError,TypeError,KeyError):kickoff=''
            rows.append(f'<tr class="{tier}" data-search="{html.escape(e["name"],quote=True)}" data-event-id="{html.escape(str(e["eventId"]))}" data-finished="{1 if actual is not None else 0}" data-kickoff="{kickoff}" data-confidence="{p}" data-odds="{c["price"] if c else 0}" data-mbs="{html.escape(mbs if mbs != "—" else "")}" data-pick="{html.escape(pick_filter,quote=True)}" data-time="{html.escape(e.get("time") or "99:99")}">{cells}</tr>')
        state='Başlangıç günü · 14 günlük bağımsız ölçüme dahil değil.' if preview else 'Sabit model · bağımsız izleme · ana kıyas ilk %50.'
        provenance=read(root/'control-provenance.json') if (root/'control-provenance.json').exists() else {}
        updated=provenance.get('completedAt') or book.get('createdAt','')
        body=f'<h1>{title} · {target}</h1><p>{html.escape(state)} Oranı bulunan seçeneklerden en yüksek güvenli tercih ve uyumlu skor.</p><p>{len(es)} maç · sonuçlanan tercihler {finished} · doğru {hits}. Son kontrol: {html.escape(updated)}</p>'
        body+='<nav><button id="sort-time" type="button" aria-pressed="false">Saate göre</button><button id="sort-confidence" type="button" aria-pressed="true">Güvene göre ↓</button><span id="sort-status">Güven: yüksekten düşüğe</span></nav>'
        body+='<div class="odds-filter"><label for="match-search">Maç ara</label><input id="match-search" type="search" placeholder="Takım veya maç adı" autocomplete="off"><label for="min-odds">En düşük oran</label><input id="min-odds" type="number" inputmode="decimal" min="1" step="0.05" placeholder="Örn. 1.50"><label for="mbs-filter">MBS</label><select id="mbs-filter"><option value="">Tümü</option><option value="1">1</option><option value="2">2</option><option value="3">3</option></select><label for="pick-filter">Tercih</label><select id="pick-filter"><option value="">Tümü</option></select><label class="check-filter"><input id="hide-finished" type="checkbox"> Sonuçlananları gizle</label><label class="check-filter" title="İstanbul saatine ve planlanan başlangıca göre"><input id="hide-started" type="checkbox"> Başlamışları gizle</label><button id="clear-odds" type="button">Filtreleri temizle</button><span id="filter-count" aria-live="polite"></span></div>'
        if target>='2026-10-28':
            old_controls='<label for="mbs-filter">MBS</label><select id="mbs-filter"><option value="">Tümü</option><option value="1">1</option><option value="2">2</option><option value="3">3</option></select><label for="pick-filter">Tercih</label><select id="pick-filter"><option value="">Tümü</option></select>'
            new_controls='<fieldset id="mbs-filter" class="multi-filter"><legend>MBS</legend>'+''.join('<label><input type="checkbox" value="'+v+'">'+v+'</label>' for v in ('1','2','3'))+'</fieldset><fieldset id="pick-filter" class="multi-filter"><legend>Tercih</legend></fieldset><small class="filter-help">Birden fazla seçebilirsin. Seçim yoksa tümü gösterilir.</small>'
            body=body.replace(old_controls,new_controls)
        body+='<div class="legend"><span class="tier-25">İlk %25</span><span class="tier-50">Sonraki %25</span><span class="tier-75">Üçüncü %25</span><span>Son %25</span></div>'
        body+=f'<section id="{sport}"><table class="match-table"><tbody class="match-list" id="matches-{sport}">'+''.join(rows)+'</tbody></table></section>'
        body+='<details><summary>Bilgi</summary><p>Güven, model olasılığıdır; gerçekleşmiş isabet garantisi değildir. Oranlar ilk kayıttandır, canlı değildir. Eksik oran/MBS “—” gösterilir. Sonuçlar yalnız tamamlanmış HTTP kayıtlarından gelir; canlı/eksik sonuçlar başarı paydasına girmez. Renkler güven sırasını gösterir. Kontrol tahminleri ve modeli değiştirmez.</p></details>'
        css=STYLE+'tr[hidden]{display:none!important}.odds-filter{display:flex;align-items:center;flex-wrap:wrap;gap:10px;margin:14px 0}.odds-filter input,.odds-filter select{width:115px;padding:10px;font:inherit;border:1px solid #b7c6d2;border-radius:8px;background:white;color:#173d57}.odds-filter #match-search{width:260px;max-width:100%;flex:1 1 220px;min-width:0}.odds-filter #pick-filter{width:auto;max-width:210px}.odds-filter button{padding:10px}.odds-filter .check-filter{display:flex;align-items:center;gap:7px}.odds-filter input[type=checkbox]{width:20px;height:20px;accent-color:#206184}' +'.bet-meta{display:block;font:500 12px/1.5 system-ui;color:#64788c;margin-top:7px}.bet-meta b{font-size:13px;color:#173d57}.match-list td:nth-child(7){display:none}'
        css+='.multi-filter{display:flex;flex-wrap:wrap;gap:8px;border:1px solid #b7c6d2;border-radius:10px;padding:10px;min-width:0;max-width:100%;margin:0}.multi-filter legend{font-weight:600;padding:0 5px}.multi-filter label{display:flex;align-items:center;gap:6px;padding:6px 9px;background:#eef4f8;border-radius:8px;min-height:32px;cursor:pointer}.filter-help{flex-basis:100%;color:#64788c}'
        doc='<!doctype html><html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+title+' · '+target+'</title><style>'+css+'</style></head><body><main>'+body+'</main>'+SCRIPT+(FILTER_SCRIPT if target>='2026-10-28' else LEGACY_FILTER_SCRIPT)+'</body></html>'
        name=folder+'-yeni.html';(root/name).write_text(doc)
        summary[folder]={'file':name,'sha256':sha(root/name),'fixtureCount':len(es),'settledChoiceCount':finished,'hits':hits}
    for name,digest in before.items():
        if sha(root/name)!=digest:raise ValueError('Presentation changed frozen forecast/model')
    manifest={'targetDate':target,'version':config['version'],'modelSha256':model_hash,'snapshotSha256':sha(source),'snapshotFile':source.name,'snapshotCreatedAt':priced.get('createdAt'),'selectionPolicy':priced['policy'],'pricedSnapshotSha256':priced['snapshotSha256'],'previewOnly':preview,'firstIndependentDate':config['first_forecast_date'],'updatedAt':updated,'reports':summary}
    (root/'new-report-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    return manifest

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();reports(a.output)
