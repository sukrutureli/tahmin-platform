"""Presentation only: preserve saved forecast values and split sports for mobile."""
import html
import re
import math

STYLE = '''
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0 auto;padding:20px 16px 64px;max-width:1120px;background:#f3f6fa;color:#172a40;font:15px/1.55 system-ui,-apple-system,sans-serif;overflow-wrap:anywhere}h1{background:#11283e;color:white;border-radius:20px;padding:30px 24px;font-size:clamp(24px,5vw,34px);line-height:1.25;margin:0 0 20px;letter-spacing:-.7px}h2{font-size:22px;margin:30px 0 12px}p{color:#526477}a{color:#006e68}nav{display:flex;flex-wrap:wrap;gap:8px;margin:20px 0}button,.sport-links a{border:1px solid #c7d6e3;border-radius:12px;background:white;padding:12px 16px;min-height:44px;color:#18354f;font:600 14px system-ui;text-decoration:none;cursor:pointer}button[aria-pressed=true]{background:#006e68;color:white;border-color:#006e68}#sort-status{display:block;width:100%;font-size:13px;color:#60748a}.sport-links{display:flex;gap:8px;margin-bottom:24px}.sport-links a{flex:1;text-align:center}.sport-heading{display:flex;align-items:center;justify-content:space-between;gap:12px}.sport-heading small{font-size:13px;background:#e0e9f1;padding:5px 10px;border-radius:99px;font-weight:500}section{overflow:visible}.match-table{width:100%;border-collapse:separate;border-spacing:0}.match-table thead{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)}.match-list{display:grid;grid-template-columns:1fr 1fr;gap:14px}.match-list tr{display:grid;grid-template-columns:1fr 1fr;background:white;border:1px solid #dce5ec;border-radius:16px;padding:16px;gap:10px 14px;min-width:0;box-shadow:0 3px 9px #18354f06}.match-list td{display:block;border:0;padding:0;white-space:normal;font-size:13px;min-width:0}.match-list td:before{content:attr(data-label);display:block;color:#77899a;font-size:11px;margin-bottom:3px}.match-list td:nth-child(2){display:none}.match-list td:nth-child(1){grid-column:1/-1;color:#60748a;font-weight:650;font-size:12px}.match-list td:nth-child(1):before{display:none}.match-list td:nth-child(3){grid-column:1/-1;font-size:17px;font-weight:750;color:#19334e;line-height:1.4;padding-bottom:10px;border-bottom:1px solid #eef2f6}.match-list td:nth-child(3):before{display:none}.match-list td:nth-child(4){color:#006e68;font-weight:750;font-size:17px}.match-list td:nth-child(5){font-size:21px;font-weight:750;font-variant-numeric:tabular-nums}.match-list td:nth-child(6){color:#006e68;font-size:19px;font-weight:750}.match-list td:nth-child(10),.match-list td:nth-child(11){font-size:11px;color:#64788b}.match-list td:nth-child(10){padding-top:8px;border-top:1px solid #eef2f6}.match-list td:nth-child(11){padding-top:8px;border-top:1px solid #eef2f6}table:not(.match-table){width:100%;border-collapse:collapse;background:white;border-radius:12px;margin:16px 0}table:not(.match-table) td,table:not(.match-table) th{padding:10px;text-align:left;border-bottom:1px solid #e3ebf1;font-size:13px;white-space:normal}hr{border:0;border-top:1px solid #d7e2ec;margin:36px 0}details{background:white;border:1px solid #dce5ec;padding:14px;border-radius:12px;margin:14px 0}summary{cursor:pointer;font-weight:650}section[id]{scroll-margin-top:12px}
.match-list td:nth-child(10){display:none}.match-list tr.tier-25{border-left:5px solid #008577;background:#f3fcf9}.match-list tr.tier-50{border-left:5px solid #4782cf;background:#f6f9ff}.match-list tr.tier-75{border-left:5px solid #c38a30;background:#fffaf1}.match-list tr.tier-rest{border-left:5px solid #9aa8b5}.match-list tr.tier-late{border-left:5px dashed #9aa8b5;background:#f4f5f7}.legend{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}.legend span{font-size:11px;border-radius:6px;padding:5px 8px;background:white;border-left:4px solid #9aa8b5}.legend .tier-25{border-color:#008577}.legend .tier-50{border-color:#4782cf}.legend .tier-75{border-color:#c38a30}.legend .tier-late{border-left-style:dashed}.legend-note{font-size:12px;margin:8px 0}
@media(max-width:650px){body{padding:14px 12px 48px}.match-list{grid-template-columns:1fr;gap:12px}h1{padding:24px 20px}.match-list tr{padding:15px;gap:9px 14px}table:not(.match-table) thead{display:none}table:not(.match-table),table:not(.match-table) tbody{display:block}table:not(.match-table) tr{display:grid;grid-template-columns:1fr 1fr;gap:8px;padding:12px;border-bottom:1px solid #dce5ec}table:not(.match-table) td{display:block;min-width:0;border:0;padding:0}table:not(.match-table) td:before{content:attr(data-label);display:block;font-size:11px;color:#77899a}table:not(.match-table) td:first-child{grid-column:1/-1;font-weight:700}#sort-status{font-size:12px}}
'''
SCRIPT = '''<script>
function order(mode){
 document.querySelectorAll('.match-list').forEach(body=>{
 const rows=Array.from(body.rows);
 rows.sort((a,b)=>mode==='confidence'?Number(b.dataset.confidence)-Number(a.dataset.confidence)||a.dataset.time.localeCompare(b.dataset.time):a.dataset.time.localeCompare(b.dataset.time)||Number(b.dataset.confidence)-Number(a.dataset.confidence));
 rows.forEach(row=>body.appendChild(row));});
 document.getElementById('sort-time').setAttribute('aria-pressed',String(mode==='time'));
 document.getElementById('sort-confidence').setAttribute('aria-pressed',String(mode==='confidence'));
 document.getElementById('sort-status').textContent=mode==='confidence'?'Güven: yüksekten düşüğe · her spor ayrı':'Saat: erkenden geçe · her spor ayrı';
}
document.getElementById('sort-time').addEventListener('click',()=>order('time'));
document.getElementById('sort-confidence').addEventListener('click',()=>order('confidence'));
</script>'''

def mobile_report(document):
    match=re.search(r'<section><table>(<thead>.*?</thead>)<tbody id="matches">(.*?)</tbody></table></section>',document,re.S)
    if not match:raise ValueError('Expected saved prediction table absent')
    headers=[html.unescape(x) for x in re.findall(r'<th>(.*?)</th>',match[1],re.S)]
    groups={'Futbol':[],'Basketbol':[]}
    for row in re.findall(r'<tr\b.*?</tr>',match[2],re.S):
        cells=re.findall(r'<td>(.*?)</td>',row,re.S)
        if len(cells)!=len(headers) or cells[1] not in groups:raise ValueError('Unexpected forecast row')
        i=iter(headers)
        row=re.sub(r'<td>',lambda _: '<td data-label="'+html.escape(next(i),quote=True)+'">',row)
        groups[cells[1]].append(row)
    for sport,rows in groups.items():
        eligible=[r for r in rows if 'Geç tahmin · kapsam dışı' not in r]
        ranked=sorted(eligible,key=lambda r:-float(re.search(r'data-confidence="([^"]+)"',r)[1]))
        tiers={r:('tier-25' if i<math.ceil(len(ranked)*.25) else 'tier-50' if i<math.ceil(len(ranked)*.5) else 'tier-75' if i<math.ceil(len(ranked)*.75) else 'tier-rest') for i,r in enumerate(ranked)}
        groups[sport]=[r.replace('<tr ', '<tr class="'+tiers.get(r,'tier-late')+'" ',1) for r in rows]
    tables='' 
    for sport,anchor in [('Futbol','football'),('Basketbol','basketball')]:
        tables+=f'<section id="{anchor}"><h2 class="sport-heading">{sport}<small>{len(groups[sport])} maç</small></h2><table class="match-table">'+match[1]+f'<tbody class="match-list" id="matches-{anchor}">'+''.join(groups[sport])+'</tbody></table></section>'
    document=document[:match.start()]+tables+document[match.end():]
    document=re.sub(r'<style>.*?</style>','<style>'+STYLE+'</style>',document,flags=re.S)
    document=re.sub(r'<script>.*?</script>',SCRIPT,document,flags=re.S)
    document=document.replace('<nav aria-label="Maç sıralaması">','<div class="sport-links"><a href="#football">Futbol · '+str(len(groups['Futbol']))+'</a><a href="#basketball">Basketbol · '+str(len(groups['Basketbol']))+'</a></div><nav aria-label="Maç sıralaması">')
    legend='<div class="legend" aria-label="Güven grupları"><span class="tier-25">En yüksek %25</span><span class="tier-50">Sonraki %25</span><span class="tier-75">Üçüncü %25</span><span class="tier-rest">Son %25</span><span class="tier-late">Geç kayıt</span></div><p class="legend-note">Renkler her sporun maç öncesi güven sırasını gösterir; isabet yüzdesi değildir.</p>'
    document=document.replace('<section id="football">',legend+'<section id="football">')
    # Keep methodology available without filling the first phone screen.
    document=re.sub(r'(<h1>.*?</h1>)(<p>Tüm maçlar listelenir\..*?</p>)',r'\1<details><summary>Tahminleri nasıl okumalıyım?</summary>\2</details>',document,flags=re.S)
    def label_table(m):
        table=m[0]
        if 'class="match-table"' in table:return table
        head=re.search(r'<thead>(.*?)</thead>',table,re.S)
        if not head:return table
        hs=re.findall(r'<th>(.*?)</th>',head[1],re.S)
        def label_row(r):
            i=iter(hs)
            return re.sub(r'<td>',lambda _: '<td data-label="'+html.escape(html.unescape(next(i,'')),quote=True)+'">',r[0])
        return re.sub(r'<tr><td>.*?</tr>',label_row,table,flags=re.S)
    return re.sub(r'<table\b.*?</table>',label_table,document,flags=re.S)
