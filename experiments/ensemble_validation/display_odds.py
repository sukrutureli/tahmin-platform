"""Presentation only: attach initial market odds/MBS without changing saved forecasts."""
import argparse,hashlib,html,json,math,re
from pathlib import Path

KEYS={'football':{'MS':['ms1','msX','ms2'],'OU':['over25','under25'],'BTTS':['bttsYes','bttsNo']},
      'basketball':{'MS':['ms1','ms2'],'OU':['over','under']}}

def valid_number(v,minimum):
    return not isinstance(v,bool) and isinstance(v,(int,float)) and math.isfinite(v) and v>minimum

def display_values(row,market,option):
    odds=row.get('odds',{});keys=KEYS.get(row.get('sport'),{}).get(market,[])
    value=odds.get(keys[option]) if isinstance(option,int) and 0<=option<len(keys) else None
    price=f'{value:.2f}' if valid_number(value,1) else '—'
    mbs=next((x for x in [odds.get('mbs'),row.get('mbs')] if valid_number(x,0) and int(x)==x),None)
    return price,str(int(mbs)) if mbs is not None else '—'

def text(s):return html.unescape(re.sub('<[^>]+>','',s)).strip()

def enrich_rows(body,expected,replay,name_index,choice_field=False):
    rows=list(re.finditer(r'<tr\b[^>]*>.*?</tr>',body,re.S))
    if len(rows)!=len(expected):raise ValueError('Display row count does not match frozen fixture IDs')
    output=[];last=0
    for match,e in zip(rows,expected):
        row=match[0];cells=list(re.finditer(r'<td\b[^>]*>(.*?)</td>',row,re.S))
        if len(cells)<=name_index or text(re.sub(r'<span class="bet-meta".*?</span>','',cells[name_index][1],flags=re.S))!=e['name']:
            raise ValueError('Display order does not match frozen fixture ID')
        source=replay.get((e['sport'],e['date'],str(e['eventId'])))
        if source is None:raise ValueError('Frozen odds source missing')
        chosen=e.get('chosen') if choice_field else {'market':e['market'],'option':e['optionIndex']}
        if not chosen:raise ValueError('Frozen market selection missing')
        price,mbs=display_values(source,chosen['market'],chosen['option'])
        meta=f'<span class="bet-meta">Oran <b>{price}</b><i>·</i>MBS <b>{mbs}</b></span>'
        cell=cells[name_index];clean=re.sub(r'<span class="bet-meta".*?</span>','',cell[0],flags=re.S)
        replaced=clean[:-5]+meta+'</td>'
        row=row[:cell.start()]+replaced+row[cell.end():]
        row=re.sub(r' data-event-id="[^"]*"','',row)
        row=row.replace('<tr','<tr data-event-id="'+html.escape(str(e['eventId']),quote=True)+'"',1)
        output.append(body[last:match.start()]+row);last=match.end()
    return ''.join(output)+body[last:]

CSS='<style id="bet-meta-style">.bet-meta{display:flex;gap:7px;align-items:center;font:500 12px/1.5 system-ui;color:#64788c;margin-top:7px;white-space:nowrap}.bet-meta b{font-size:13px;color:#173d57}.bet-meta i{font-style:normal;color:#a0afbd}</style>'

def render(root):
    root=Path(root);replay={};hashes={}
    for sport in KEYS:
        p=root/(sport+'-replay.json');hashes[p.name]=hashlib.sha256(p.read_bytes()).hexdigest()
        for r in json.loads(p.read_text()):replay[(sport,r['date'],str(r['eventId']))]=dict(r,sport=sport)
    outputs=[]
    source=root/'match-choice-before-results.json'
    if source.exists() and (root/'best-matches.html').exists():
        saved=json.loads(source.read_text());hashes[source.name]=hashlib.sha256(source.read_bytes()).hexdigest()
        doc=(root/'best-matches.html').read_text()
        for sport in KEYS:
            es=sorted([e for e in saved['predictions'] if e['sport']==sport],key=lambda e:(e.get('time') or '99:99',e['eventId']))
            pat=r'(<tbody class="match-list" id="matches-'+sport+r'">)(.*?)(</tbody>)'
            def replace(m):return m[1]+enrich_rows(m[2],es,replay,2)+m[3]
            doc,n=re.subn(pat,replace,doc,flags=re.S)
            if n!=1:raise ValueError('Expected mobile sport table missing')
        if 'id="bet-meta-style"' not in doc:doc=doc.replace('</style>','</style>'+CSS,1)
        (root/'best-matches.html').write_text(doc);outputs.append('best-matches.html')
    source=root/'stability-before-results.json'
    if source.exists() and (root/'stability.html').exists():
        saved=json.loads(source.read_text());hashes[source.name]=hashlib.sha256(source.read_bytes()).hexdigest();doc=(root/'stability.html').read_text()
        for sport,systems in saved['systems'].items():
            es=sorted(systems[saved['version']],key=lambda e:(e.get('time') or '',e['eventId']))
            pat=r'(<h2>'+sport+r'</h2>\s*(?:<section\b[^>]*>)?<table[^>]*>.*?<tbody[^>]*>)(.*?)(</tbody>)'
            def replace(m):return m[1]+enrich_rows(m[2],es,replay,1,True)+m[3]
            doc,n=re.subn(pat,replace,doc,flags=re.S)
            if n!=1:raise ValueError('Expected locked sport table missing')
        if 'id="bet-meta-style"' not in doc:doc=doc.replace('</style>','</style>'+CSS,1)
        (root/'stability.html').write_text(doc);outputs.append('stability.html')
    for name,digest in hashes.items():
        if hashlib.sha256((root/name).read_bytes()).hexdigest()!=digest:raise ValueError('Frozen display source changed')
    (root/'display-metadata.json').write_text(json.dumps({'policy':'Initial saved odds only; not live prices. Missing/zero odds and missing MBS are shown as an em dash. Fixture IDs follow verified original row order. No forecast or selection changed.','sourceHashes':hashes,'outputs':outputs},ensure_ascii=False,indent=2)+'\n')
    return outputs

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);a=p.parse_args();render(a.output)
