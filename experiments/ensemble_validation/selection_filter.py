"""Presentation-only selection filtering; frozen forecasts remain untouched."""
import re

CHOICE_SCRIPT = r'''
const choiceViews=new Map();
for(const row of rows){
 const tiles=[...row.querySelectorAll('.market-option.chosen')];
 const cell=row.querySelector('[data-label="Sonuç"]');
 const states=(cell?.innerHTML||'').split(/<br\s*\/?\s*>/i);
 const picks=JSON.parse(row.dataset.picks||'[]');
 const items=tiles.map((tile,i)=>({tile,pick:picks[i],price:Number(tile.querySelector('small').textContent.replace(',','.')),caption:tile.querySelector('span').textContent,status:states[i]||states[0]||'',outcome:'pending'}));
 for(const item of items){const s=item.status;item.outcome=/Tuttu|Kazandı/.test(s)?'won':/Yattı|Kaybetti/.test(s)?'lost':/İade|doğrulanmadı/.test(s)?'unverified':'pending';}
 const meta=row.querySelector('.bet-meta');
 choiceViews.set(row,{items,cell,meta,originalMeta:meta?.innerHTML||'',originalStatus:cell?.innerHTML||''});
}
function filterChoices(row,min,pickValues){
 const view=choiceViews.get(row),items=view.items;
 const visible=items.filter(item=>(min===null||!Number.isFinite(min)||(item.price>1&&item.price>=min))&&(!pickValues.length||pickValues.includes(item.pick)));
 for(const item of items)item.tile.hidden=!visible.includes(item);
 if(view.cell)view.cell.innerHTML=items.length?visible.map(item=>item.status).join('<br>'):view.originalStatus;
 if(view.meta){
  view.meta.innerHTML='';
  for(const item of visible){const line=document.createElement('span');line.style.display='block';line.textContent=item.caption+': '+item.price.toFixed(2);view.meta.appendChild(line);}
  const mbs=document.createElement('span');mbs.textContent='MBS '+(row.dataset.mbs||'—');view.meta.appendChild(mbs);
  if(!items.length)view.meta.innerHTML=view.originalMeta;
 }
 const states=visible.map(item=>item.outcome);
 row.dataset.visibleMatchOutcome=!states.length?'no-choice':states.includes('pending')?'pending':states.includes('unverified')?'unverified':states.includes('won')&&states.includes('lost')?'partial':states[0];
 return items.length?visible.length>0:(min===null&&!pickValues.length);
}
'''

def upgrade_rule_html(doc):
    if 'const choiceViews=new Map();' in doc:return doc
    # Only the rules renderer has match-based outcomes and selection metadata.
    if 'data-match-outcome=' not in doc:return doc
    start=doc.rfind('<script>')
    if start<0:raise ValueError('Missing filter script')
    head,script=doc[:start],doc[start:]
    marker='function filter(){'
    if marker not in script:raise ValueError('Missing filter function')
    script=script.replace(marker,CHOICE_SCRIPT+'\n'+marker,1)
    old='below=min!==null&&Number.isFinite(min)&&!(odd>1&&odd>=min)'
    if old not in script:raise ValueError('Missing expected odds filter')
    script=script.replace(old,'below=!filterChoices(row,min,pickValues)',1)
    script=re.sub(r'wrongPick=pickValues\.length>0&&!JSON\.parse\(row\.dataset\.picks\|\|\x27\[\]\x27\)\.some\(p=>pickValues\.includes\(p\)\)', 'wrongPick=false',script,count=1)
    script=script.replace("row.dataset.matchOutcome||'pending'","row.dataset.visibleMatchOutcome||row.dataset.matchOutcome||'pending'")
    head=head.replace('</style>','.market-option[hidden]{display:none!important}</style>',1)
    return head+script
