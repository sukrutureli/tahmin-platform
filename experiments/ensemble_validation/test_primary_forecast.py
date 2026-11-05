import json,tempfile,unittest,hashlib
from pathlib import Path
from unittest.mock import patch
from datetime import datetime,timezone,date
import locked_stability as locked
from primary_forecast import forecast
from publish_primary import prepare,publish
import test_locked_stability as fixtures
from test_locked_stability import C
from report import BASE
from prepare import dump
class PrimaryTests(unittest.TestCase):
    def test_frozen_inference_has_no_research_fit_dependency(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/'out';previous=Path(td)/'previous';root.mkdir();previous.mkdir()
            fixture=fixtures.LockedStabilityTests();fixture.source(previous);locked.initialize(previous,None,C)
            day=datetime.now(timezone.utc).astimezone(__import__('zoneinfo').ZoneInfo('Europe/Istanbul')).date().isoformat()
            current={}
            for sport in ('football','basketball'):
                row={'date':day,'eventId':'1','name':'A - B','time':'23:59','realScore':None,'variants':{'legacy':{'models':{BASE[sport]:{}}}},'odds':{'ms1':1.8,'ms2':2.,'msX':3.,'over25':1.8,'under25':1.8,'bttsYes':1.8,'bttsNo':1.8,'hOverUnderValue':160.5,'over':1.8,'under':1.8}}
                current[sport]=[row];dump(root/(sport+'-replay.json'),[row])
            dump(root/'live-history-journal.json',[]);dump(root/'live-history.json',{'fixtures':[],'requests':[]})
            with patch('primary_forecast.build_ledger',return_value=({'matches':[],'identities':[]},{})),patch('primary_forecast.candidate_vector',side_effect=lambda r,s,m,c:[.7,.2,.1] if s=='football' and m=='MS' else [.7,.3]),patch('primary_forecast.parse_score',return_value=[2,1]),patch('locked_stability.features',return_value={}),patch('locked_stability.predict',side_effect=fixture.prediction),patch('outcome_learning.learn',side_effect=AssertionError('No training')),patch('context_experiment.learn_context',side_effect=AssertionError('No context fitting')):
                forecast(root,previous,day,enrich=False)
            snapshot=locked.verify_snapshot(root,C);self.assertEqual((root/locked.MODEL).read_bytes(),(previous/locked.MODEL).read_bytes())
            self.assertEqual(snapshot['systems']['football'][C['version']][0]['markets']['MS'],[.8,.1,.1])
            self.assertEqual(snapshot['contextSnapshotSha256'],hashlib.sha256((root/'primary-context-before-results.json').read_bytes()).hexdigest())
            saved=(root/locked.SNAPSHOT).read_bytes()
            with patch('locked_stability.predict',side_effect=AssertionError('No second forecast')):forecast(root,previous,day,enrich=False)
            self.assertEqual((root/locked.SNAPSHOT).read_bytes(),saved)
            files,m=prepare(root,day);self.assertEqual(set(files),{'futbol.html','basketbol.html'})
            (root/'futbol-yeni.html').write_text('changed')
            with self.assertRaises(ValueError):prepare(root,day)
    def test_private_only_and_existing_final_no_overwrite(self):
        manifest={'targetDate':'2026-11-06','modelSha256':'a','snapshotSha256':'b','pricedSnapshotSha256':'c','selectionPolicy':'complete-market-price-v2','reports':{}}
        class API:
            private=True
            def call(self,path,*args):
                if path.endswith('/git/ref/heads/main'):return {'object':{'sha':'a'}}
                if '/git/commits/' in path:return {'tree':{'sha':'t'}}
                if '/git/trees/' in path:return {'tree':[{'path':'deney/reports/2026-11-06/checkpoint-manifest.json'}]}
                return {'private':self.private}
        api=API();self.assertFalse(publish(api,{},manifest,'1',2,date(2026,11,6)))
        api.private=False
        with self.assertRaises(ValueError):publish(api,{},manifest,'1',2,date(2026,11,6))
