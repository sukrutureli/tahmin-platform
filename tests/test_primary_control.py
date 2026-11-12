import base64,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,'scripts')
sys.path.insert(0,'experiments/ensemble_validation')
import primary_control as m
class PrimaryControlTests(unittest.TestCase):
 def run(self,*a,**k):return super().run(*a,**k)
 def test_completed_sports_allow_failed_legacy_publish(self):
  r={'path':'.github/workflows/control.yml','head_branch':'main','status':'completed','conclusion':'failure','head_repository':{'full_name':m.SOURCE}}
  jobs=[{'name':n,'conclusion':'success'} for n in ['Football CONTROL','Basketball CONTROL']]
  m.verify_control(r,jobs)
  jobs[1]['conclusion']='failure'
  with self.assertRaises(ValueError):m.verify_control(r,jobs)
 def test_istanbul_control_boundary(self):
  self.assertEqual(m.target({'created_at':'2026-11-11T23:00:00Z'}),'2026-11-11')
  self.assertEqual(m.target({'created_at':'2026-11-12T09:00:00Z'}),'2026-11-12')
 def test_only_matching_dated_fixtures_receive_finished_labels(self):
  rows=[{'date':'2026-11-12','eventId':'1','choice':'fixed'},{'date':'2026-11-11','eventId':'2'}]
  n=m.apply_results(rows,[{'eventId':'1','score':'2-1'},{'eventId':'2','score':'3-0'},{'eventId':'new','score':'1-0'},{'eventId':'bad','score':'LIVE'}],'2026-11-12')
  self.assertEqual(n,1);self.assertEqual(rows[0]['choice'],'fixed');self.assertEqual(rows[0]['realScore'],'2-1');self.assertNotIn('realScore',rows[1])
 def test_conflicting_results_rejected(self):
  with self.assertRaises(ValueError):m.apply_results([],[{'eventId':'1','score':'2-1'},{'eventId':'1','score':'1-0'}],'2026-11-12')
 def test_exact_date_is_required(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'futbol/data';p.mkdir(parents=True);(p/'RealScores-2026-11-11.json').write_text('[]')
   with self.assertRaises(ValueError):m.results_file(Path(td),'futbol','2026-11-12')
 def test_frozen_guard_detects_mutation(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);(p/'stability-before-results.json').write_text('old');before=m.protected(p)
   (p/'stability-before-results.json').write_text('changed')
   self.assertNotEqual(before,m.protected(p))
 def test_canonical_publisher_is_scoped_and_does_not_rewrite_ready(self):
  from datetime import date
  day='2026-11-12';origin={'sourceRunId':'10','sourceArtifactId':11,'snapshotSha256':'snap','pricedSnapshotSha256':'priced'}
  class Fake:
   def __init__(self):self.writes=[]
   def call(self,path,method='GET',body=None):
    if method!='GET':self.writes.append((path,body));return {'sha':'new'}
    if path==m.DEST:return {'private':True}
    if '/git/ref/' in path:return {'object':{'sha':'head'}}
    if '/git/commits/' in path:return {'tree':{'sha':'tree'}}
    if '/contents/' in path:return {'content':base64.b64encode(json.dumps(origin).encode()).decode()}
    return {'tree':[],'truncated':False}
  a=Fake();manifest={'modelSha256':'model','pricedSnapshotSha256':'priced','reports':{}}
  with patch('publish_primary.prepare',return_value=({'futbol.html':'football','basketbol.html':'basketball'},manifest)):
   m.publish(a,Path('.'),{'targetDate':day,'controlRunId':'20','origin':origin},manifest,{},'renderer',date.fromisoformat(day))
  paths=next(body['tree'] for path,body in a.writes if path.endswith('/git/trees'))
  self.assertEqual({x['path'] for x in paths},{'raporlar/'+day+'/'+n for n in ['futbol.html','basketbol.html','primary-control.json']})
 def test_workflow_has_no_research_or_training_dependency(self):
  import yaml
  w=yaml.safe_load(Path('.github/workflows/primary-control.yml').read_text())
  j=w['jobs']['refresh'];self.assertNotIn('needs',j)
  runs='\n'.join(s.get('run','') for s in j['steps'])
  self.assertNotIn('freeze',runs);self.assertNotIn('mine_rules',runs);self.assertNotIn('mvn',runs)
if __name__=='__main__':unittest.main()
