import hashlib,json,tempfile,unittest
from pathlib import Path
from new_reports import reports

class NewReportTests(unittest.TestCase):
    def test_two_sports_and_results_are_rendered_without_changing_any_frozen_source(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);model={'protocol':{'version':'opponent-locked-v1','first_forecast_date':'2026-10-19'},'payload':{'footballDistribution':{'dispersion':None,'rho':0},'basketballCovariance':[[100,0],[0,100]]}}
            (root/'stability-model.json').write_text(json.dumps(model));digest=hashlib.sha256((root/'stability-model.json').read_bytes()).hexdigest()
            systems={}
            for sport,score in [('football',[1,0]),('basketball',[80,70])]:
                entry={'sport':sport,'date':'2026-10-19','eventId':'42','name':sport+' Home - Away','time':'20:00','prospectiveBeforeKickoff':True,'score':score,'scoreMean':score,'markets':{'MS':[.7,.2,.1] if sport=='football' else [.7,.3]},'chosen':{'market':'MS','option':0,'confidence':.7}}
                systems[sport]={'opponent-locked-v1':[entry]}
                (root/(sport+'-replay.json')).write_text(json.dumps([{'date':'2026-10-19','eventId':'42','realScore':'-'.join(map(str,score)),'odds':{'ms1':1.8,'mbs':2}}]))
            (root/'stability-before-results.json').write_text(json.dumps({'targetDate':'2026-10-19','version':'opponent-locked-v1','modelSha256':digest,'systems':systems,'createdAt':'2026-10-18T22:00:00Z'}))
            before={p.name:p.read_bytes() for p in root.iterdir()}
            manifest=reports(root)
            self.assertFalse(manifest['previewOnly']);self.assertEqual(manifest['reports']['futbol']['fixtureCount'],1)
            for folder,sport in [('futbol','football'),('basketbol','basketball')]:
                s=(root/(folder+'-yeni.html')).read_text();self.assertIn(sport+' Home',s);self.assertIn('Oran <b>1.80</b>',s);self.assertIn('MBS <b>2</b>',s);self.assertIn('Kazandı',s);self.assertIn('id="min-odds"',s);self.assertIn('data-odds="1.8"',s)
            self.assertEqual(before,{n:(root/n).read_bytes() for n in before})
    def test_later_day_cannot_use_unlocked_research_forecasts(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);(root/'context-before-results.json').write_text('{"targetDate":"2026-10-19"}')
            with self.assertRaisesRegex(ValueError,'Missing locked'):reports(root)

if __name__=='__main__':unittest.main()
