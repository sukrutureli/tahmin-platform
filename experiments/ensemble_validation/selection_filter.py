"""Presentation-only selection filtering; frozen forecasts remain untouched."""
import re

CHOICE_SCRIPT = r'''
const choiceFilterVersion=2;
function choiceOutcome(items){
 const states=items.map(item=>item.outcome);
 return !states.length?'no-choice':states.includes('pending')?'pending':states.includes('unverified')?'unverified':states.includes('won')&&states.includes('lost')?'partial':states[0];
}
const choiceViews=new Map();
for(const row of rows){
 const tiles=[...row.querySelectorAll('.market-option.chosen')];
 const cell=row.querySelector('[data-label="Sonuç"]');
 const states=(cell?.innerHTML||'').split(/<br\s*\/?\s*>/i);
 const picks=JSON.parse(row.dataset.picks||'[]');
 const items=tiles.map((tile,i)=>({tile,pick:picks[i],price:Number(tile.querySelector('small').textContent.replace(',','.')),caption:tile.querySelector('span').textContent,status:states[i]||states[0]||'',outcome:'pending'}));
 for(const item of items){const s=item.status;item.outcome=/Tuttu|Kazandı/.test(s)?'won':/Yattı|Kaybetti/.test(s)?'lost':/İade|doğrulanmadı/.test(s)?'unverified':'pending';}
 const meta=row.querySelector('.bet-meta');
 choiceViews.set(row,{items,cell,meta,originalMeta:meta?.innerHTML||'',originalStatus:cell?.innerHTML||'',visibleMask:(1<<items.length)-1,visibleOutcome:choiceOutcome(items)});
}
function filterChoices(row,min,pickValues){
 const view=choiceViews.get(row),items=view.items;
 let mask=0;
 const visible=items.filter((item,i)=>{
  const show=(min===null||!Number.isFinite(min)||(item.price>1&&item.price>=min))&&(!pickValues.length||pickValues.includes(item.pick));
  if(show)mask|=1<<i;return show;
 });
 const passes=items.length?mask!==0:(min===null&&!pickValues.length);
 if(mask===view.visibleMask)return passes;
 view.visibleMask=mask;view.visibleOutcome=choiceOutcome(visible);
 // An excluded card needs no hidden DOM rebuilt. Refresh only if it becomes visible again.
 if(!passes)return false;
 if(view.cell)view.cell.innerHTML=items.length?visible.map(item=>item.status).join('<br>'):view.originalStatus;
 if(view.meta){
  view.meta.innerHTML='';
  for(const item of visible){const line=document.createElement('span');line.style.display='block';line.textContent=item.caption+': '+item.price.toFixed(2);view.meta.appendChild(line);}
  const mbs=document.createElement('span');mbs.textContent='MBS '+(row.dataset.mbs||'—');view.meta.appendChild(mbs);
  if(!items.length)view.meta.innerHTML=view.originalMeta;
 }
 return passes;
}
let pendingFilterFrame=null;
function queueFilter(){
 if(pendingFilterFrame!==null)return;
 pendingFilterFrame=requestAnimationFrame(()=>{pendingFilterFrame=null;filter();});
}
'''

def upgrade_rule_html(doc):
    if 'const choiceFilterVersion=2;' in doc:return doc
    if 'data-match-outcome=' not in doc:return doc
    start=doc.rfind('<script>')
    if start<0:raise ValueError('Missing filter script')
    head,script=doc[:start],doc[start:]
    marker='function filter(){'
    if marker not in script:raise ValueError('Missing filter function')
    if 'const choiceViews=new Map();' in script:
        a=script.index('const choiceViews=new Map();');b=script.index(marker,a)
        script=script[:a]+CHOICE_SCRIPT+'\n'+script[b:]
    else:
        script=script.replace(marker,CHOICE_SCRIPT+'\n'+marker,1)
        old='below=min!==null&&Number.isFinite(min)&&!(odd>1&&odd>=min)'
        if old not in script:raise ValueError('Missing expected odds filter')
        script=script.replace(old,'below=!filterChoices(row,min,pickValues)',1)
        script=re.sub(r'wrongPick=pickValues\.length>0&&!JSON\.parse\(row\.dataset\.picks\|\|\x27\[\]\x27\)\.some\(p=>pickValues\.includes\(p\)\)', 'wrongPick=false',script,count=1)
    script=script.replace("row.dataset.visibleMatchOutcome||row.dataset.matchOutcome||'pending'","row.dataset.matchOutcome||'pending'")
    script=script.replace("row.dataset.matchOutcome||'pending'","choiceViews.get(row)?.visibleOutcome||row.dataset.matchOutcome||'pending'")
    script=re.sub(r'row\.hidden=([^;]+);if\(!row.hidden\)n\+\+;',r'const hide=\1;if(row.hidden!==hide)row.hidden=hide;if(!hide)n++;',script,count=1)
    script=script.replace("addEventListener('input',filter)","addEventListener('input',queueFilter)").replace("addEventListener('change',filter)","addEventListener('change',queueFilter)").replace("addEventListener('focus',filter)","addEventListener('focus',queueFilter)")
    script=script.replace('setInterval(filter,30000)',"setInterval(()=>{if(started.checked)queueFilter();},30000)")
    return head+script
