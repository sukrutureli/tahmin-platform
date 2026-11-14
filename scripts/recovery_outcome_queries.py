"""Limit HTTP label refresh to already-started fixtures; preserve full saved cohort."""
import argparse,json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
def run(root,day,mode):
 root=Path(root)
 for sport in ['football','basketball']:
  replay=root/(sport+'-replay.json');rows=json.loads(replay.read_text());query=root/(sport+'-refresh-query.json')
  if mode=='prepare':
   selected=[];skipped=[];now=datetime.now(ZoneInfo('Europe/Istanbul'))
   for row in rows:
    if row.get('date')!=day or row.get('role')!='holdout':continue
    try:future=datetime.fromisoformat(day+'T'+row['time']).replace(tzinfo=ZoneInfo('Europe/Istanbul'))>now
    except (ValueError,KeyError,TypeError):future=False
    if future:skipped.append({'eventId':str(row['eventId']),'status':'not started; refresh skipped'})
    else:selected.append(row)
   query.write_text(json.dumps(selected,ensure_ascii=False)+'\n')
   (root/(sport+'-not-started-audit.json')).write_text(json.dumps(skipped)+'\n')
  else:
   fresh={(r['date'],str(r['eventId'])):r for r in json.loads(query.read_text())}
   for row in rows:
    item=fresh.get((row['date'],str(row['eventId'])))
    if item and item.get('resultSource')=='live HTTP finished scoreboard':
     row['realScore']=item['realScore'];row['resultSource']=item['resultSource']
   replay.write_text(json.dumps(rows,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
   audit=root/(sport+'-outcome-audit.json');values=json.loads(audit.read_text())+json.loads((root/(sport+'-not-started-audit.json')).read_text())
   audit.write_text(json.dumps(values,ensure_ascii=False)+'\n')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','merge']);p.add_argument('--root',type=Path,required=True);p.add_argument('--date',required=True);a=p.parse_args();run(a.root,a.date,a.mode)
