import sys,unittest,tempfile,json,hashlib
from pathlib import Path
from datetime import date
sys.path.insert(0,'scripts')
from archive_reports import archive
from parallel_experiments import launch
class Promotion(unittest.TestCase):
    def test_dated_panel_uses_verified_mobile_reports(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);d='2026-11-02';src=root/'deney/reports'/d;src.mkdir(parents=True)
            m={'targetDate':d,'selectionPolicy':'available-price-v1','version':'opponent-locked-v1','reports':{}}
            for sport in ['futbol','basketbol']:
                data=('mobile '+sport).encode();(src/(sport+'-yeni.html')).write_bytes(data)
                m['reports'][sport]={'sha256':hashlib.sha256(data).hexdigest()}
                (root/sport).mkdir();(root/sport/(sport+'.html')).write_text("<b class='day-title'>"+d+"</b>")
            (src/'new-report-manifest.json').write_text(json.dumps(m));archive(root,date.fromisoformat(d))
            self.assertEqual((root/'raporlar'/d/'futbol.html').read_text(),'mobile futbol')
            (src/'futbol-yeni.html').write_text('wrong')
            with self.assertRaises(ValueError):archive(root,date.fromisoformat(d))
    def test_workflow_dispatch_targets_main(self):
        class Api:
            def call(self,p,body=None):
                if body:self.body=body;return
                return {'workflow_runs':[]}
        a=Api();launch(a,'control','2026-11-02','7','a'*40,'8');self.assertEqual(a.body['ref'],'main')
