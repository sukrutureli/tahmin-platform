"""Primary serving must not load or serialize the cumulative research dataset."""
import ast,json,tempfile,unittest,urllib.parse,math
from pathlib import Path
from collections import defaultdict,Counter
from datetime import date,datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
def selected(path,names,env):
    tree=ast.parse(path.read_text())
    module=ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names],type_ignores=[])
    exec(compile(module,str(path),'exec'),env);return env
class ServingTests(unittest.TestCase):
    def test_target_projection_keeps_all_source_fields_and_deduplication(self):
        env={'BASE':{'football':None,'basketball':None},'result':lambda row,*args:row.get('realScore')}
        selected(ROOT/'experiments/ensemble_validation/mine_rules.py',{'merge_dataset'},env)
        selected(ROOT/'experiments/ensemble_validation/primary_forecast.py',{'serving_dataset'},env)
        target='2026-11-14'
        current={'football':[{'date':target,'eventId':1,'odds':{'MS1':1.5},'features':[1,2]},{'date':target,'eventId':2,'features':[3]},{'date':'2026-10-01','eventId':9}], 'basketball':[{'date':target,'eventId':3,'features':[4]}]}
        prior={'football':[{'date':'2026-10-02','eventId':9}], 'basketball':[]}
        expected={s:[r for r in rs if r['date']==target] for s,rs in env['merge_dataset'](current,prior,target).items()}
        self.assertEqual(env['serving_dataset'](current,target),expected)
    def test_cache_identity_validation_across_requests_and_precedence(self):
        env={'Path':Path,'json':json,'urllib':urllib,'math':math,'date':date,'datetime':datetime,'timezone':timezone,'defaultdict':defaultdict,'Counter':Counter,
             'flatten':lambda rows:rows or [],'schedule_row':lambda row,*args:row}
        selected(ROOT/'experiments/ensemble_validation/context_features.py',{'number_id','canonical','cache_records'},env)
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'http-cache/day').mkdir(parents=True);(root/'context-http-cache/day').mkdir(parents=True)
            row={'id':7,'date':'2026-11-10','opponentId':2,'venue':'home','regulationKnown':True,'for':2,'against':1,'tournamentId':3}
            for name,team,folder in [('unverified.json',None,'http-cache'),('verified.json',1,'http-cache'),('wrong.json',99,'http-cache'),('verified.json',99,'context-http-cache')]:
                (root/folder/'day'/name).write_text(json.dumps({'data':{'metaData':{'team':{'id':team}},'initialData':[row]}}))
            requests=[{'url':'https://example.test/soccer/widget/team/schedule?teId=1','status':200,'cache':name} for name in ['unverified.json','wrong.json','verified.json']]
            records,rejected=env['cache_records'](root,requests,'2026-11-14','collected')
            self.assertEqual(rejected,1);self.assertEqual(len(records),2)
            for record in records:
                self.assertEqual((record['home'],record['away'],record['homeScore'],record['awayScore']),('broadage:1','broadage:2',2,1))
if __name__=='__main__':unittest.main()
