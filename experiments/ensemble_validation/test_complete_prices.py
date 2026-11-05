import copy,json,tempfile,unittest
from datetime import datetime,timezone
from pathlib import Path
from complete_prices import choose,freeze,settle,FILE,POLICY
from new_reports import reports
class CompletePricesTests(unittest.TestCase):
    def test_incomplete_ms_falls_back_to_complete_btts(self):
        entry={'markets':{'MS':[.7,.1,.2],'OU':[.8,.2],'BTTS':[.4,.6]}}
        row={'odds':{'ms1':17.35,'msX':8.76,'ms2':0,'over25':0,'under25':0,'bttsYes':2.26,'bttsNo':1.27}}
        before=copy.deepcopy(entry);c=choose(entry,row,'football')
        self.assertEqual((c['market'],c['option']),('BTTS',1));self.assertEqual(entry,before)
        row['odds']['bttsNo']=None;self.assertIsNone(choose(entry,row,'football'))
    def test_basketball_and_invalid_numbers(self):
        e={'markets':{'MS':[.75,.25],'OU':[.53,.47]}}
        r={'odds':{'ms1':10.7,'ms2':0,'hOverUnderValue':142.5,'over':1.63,'under':1.6}}
        self.assertEqual(choose(e,r,'basketball')['market'],'OU')
        for bad in [None,0,1,float('nan'),float('inf'),True]:
            r['odds']['under']=bad;self.assertIsNone(choose(e,r,'basketball'))
    def test_complete_high_price_not_arbitrarily_capped(self):
        e={'markets':{'MS':[.7,.1,.2]}};r={'odds':{'ms1':17.,'msX':8.,'ms2':1.05}}
        self.assertEqual(choose(e,r,'football')['price'],17.)

    def test_versioned_snapshots_preserve_legacy_and_control_reuses_choices(self):
        import hashlib
        import priced_choices
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);model={'protocol':{'version':'opponent-locked-v1','first_forecast_date':'2026-10-19'},'payload':{'footballDistribution':{'dispersion':None,'rho':0},'basketballCovariance':[[100,0],[0,100]]}}
            (root/'stability-model.json').write_text(json.dumps(model));mh=hashlib.sha256((root/'stability-model.json').read_bytes()).hexdigest()
            e={'eventId':'1','name':'A - B','time':'20:00','prospectiveBeforeKickoff':True,'scoreMean':[1.5,1.2],'score':[2,1],'markets':{'MS':[.7,.1,.2],'OU':[.8,.2],'BTTS':[.4,.6]}}
            book={'targetDate':'2026-11-05','version':'opponent-locked-v1','modelSha256':mh,'createdAt':'2026-11-05T00:00:00Z','systems':{'football':{'main':[e],'opponent-locked-v1':[e]},'basketball':{'main':[],'opponent-locked-v1':[]}}}
            (root/'stability-before-results.json').write_text(json.dumps(book))
            (root/'football-replay.json').write_text(json.dumps([{'date':'2026-11-05','eventId':'1','realScore':None,'odds':{'ms1':17.35,'msX':8.76,'ms2':0,'bttsYes':2.26,'bttsNo':1.27}}]));(root/'basketball-replay.json').write_text('[]')
            now=datetime(2026,11,5,8,tzinfo=timezone.utc);priced_choices.freeze(root,now);legacy=(root/'priced-before-results.json').read_bytes()
            b=freeze(root,now);self.assertEqual(b['policy'],POLICY);self.assertEqual(b['systems']['football']['experiment'][0]['chosen']['market'],'BTTS')
            raw=(root/FILE).read_bytes();settle(root);self.assertEqual((root/FILE).read_bytes(),raw);self.assertEqual((root/'priced-before-results.json').read_bytes(),legacy)
            r=root/'football-replay.json';rows=json.loads(r.read_text());rows[0]['odds']['bttsNo']=0;r.write_text(json.dumps(rows));self.assertEqual(freeze(root),b)
