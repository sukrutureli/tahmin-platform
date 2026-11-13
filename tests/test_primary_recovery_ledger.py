"""Regression checks for exact cache and ledger semantics in serving recovery."""
import ast,json,tempfile,unittest,urllib.parse,math
from pathlib import Path
from collections import defaultdict,Counter
from datetime import date,datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
def functions(path):
    module=ast.parse(path.read_text())
    names={'number_id','canonical','merge_records','cache_records','fixture_index','build_ledger'}
    selected=ast.Module(body=[n for n in module.body if isinstance(n,ast.FunctionDef) and n.name in names],type_ignores=[])
    env={'Path':Path,'json':json,'urllib':urllib,'math':math,'date':date,'datetime':datetime,'timezone':timezone,'defaultdict':defaultdict,'Counter':Counter,
         'flatten':lambda rows:rows or [],'schedule_row':lambda row,*args:row,
         'dump':lambda path,value:path.write_text(json.dumps(value))}
    exec(compile(selected,str(path),'exec'),env);return env
class ExactLedgerTests(unittest.TestCase):
    def test_cache_global_validation_precedence_and_ledger_conflicts(self):
        original=functions(ROOT/'experiments/ensemble_validation/context_features.py')
        indexed=functions(ROOT/'scripts/context_features_fast.py')
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'http-cache/day').mkdir(parents=True);(root/'context-http-cache/day').mkdir(parents=True)
            row={'id':7,'date':'2026-11-10','opponentId':2,'venue':'home','regulationKnown':True,'for':2,'against':1,'tournamentId':3}
            def save(name,team,rows,folder='http-cache'):
                (root/folder/'day'/name).write_text(json.dumps({'data':{'metaData':{'team':{'id':team}},'initialData':rows}}))
            save('unverified.json',None,[row]);save('verified.json',1,[row]);save('mismatch.json',99,[row])
            save('verified.json',99,[],folder='context-http-cache')
            requests=[{'url':'https://example.test/soccer/widget/team/schedule?teId=1','status':200,'cache':name} for name in ['unverified.json','mismatch.json','verified.json']]
            a=original['cache_records'](root,requests,'2026-11-13','freeze')
            b=indexed['cache_records'](root,requests,'2026-11-13','freeze')
            self.assertEqual(a,b);self.assertEqual(len(b[0]),2);self.assertEqual(b[1],1)
            (root/'live-history.json').write_text(json.dumps({'requests':requests,'completedAt':'freeze'}))
            (root/'live-history-journal.json').write_text('[]')
            prior=root/'prior';prior.mkdir()
            conflict=dict(a[0][0],homeScore=99)
            (prior/'context-ledger.json').write_text(json.dumps({'matches':[conflict],'conflictingMatchKeys':[]}))
            before,bi=original['build_ledger'](root,prior,'2026-11-13')
            after,ai=indexed['build_ledger'](root,prior,'2026-11-13')
            before.pop('createdAt');after.pop('createdAt')
            self.assertEqual(before,after);self.assertEqual(bi,ai)
            self.assertEqual(after['matches'],[])
if __name__=='__main__':unittest.main()
