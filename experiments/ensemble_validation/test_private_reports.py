import hashlib,json,tempfile,unittest
from pathlib import Path
from private_reports import collect,compact,publish,DEST,PREFIX

class FakeApi:
    def __init__(self,private=True,entries=None):self.private=private;self.entries=entries or [];self.writes=[]
    def call(self,path,method='GET',body=None):
        if method!='GET':
            self.writes.append((path,method,body));return {'sha':'new'}
        if path==DEST:return {'private':self.private}
        if '/git/ref/' in path:return {'object':{'sha':'head'}}
        if '/git/commits/' in path:return {'tree':{'sha':'tree'}}
        return {'tree':self.entries,'truncated':False}

class PrivateReportTests(unittest.TestCase):
    def seed(self,root):
        for n in ['daily-evaluation.json','input-manifest.json','context-evaluation.json','stability-journal.json']:
            (root/n).write_text(json.dumps({'date':'2026-10-18','count':4,'eventIds':['private-id']}))
    def test_public_destination_is_rejected_before_any_write(self):
        api=FakeApi(False)
        with self.assertRaisesRegex(ValueError,'private'):publish(api,{'daily-evaluation.json':'{}'}, {'targetDate':'2026-10-18','sourceRunId':'1'})
        self.assertEqual(api.writes,[])
    def test_allowlist_excludes_raw_data_and_preserves_source_bytes(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);self.seed(root);(root/'rule-mining-dataset.json').write_text('sensitive dataset')
            before={p.name:p.read_bytes() for p in root.iterdir()}
            files,_=collect(root)
            self.assertNotIn('rule-mining-dataset.json',files)
            self.assertEqual(json.loads(files['daily-evaluation.json'])['count'],4)
            self.assertNotIn('eventIds',json.loads(files['daily-evaluation.json']))
            self.assertEqual(before,{p.name:p.read_bytes() for p in root.iterdir()})
    def test_bounded_diagnostics_keep_all_metrics(self):
        v=compact({'count':50,'accuracy':.6,'errors':list(range(20)),'finishedEventIds':['x']})
        self.assertEqual(v,{'count':50,'accuracy':.6,'errorExampleCount':20,'errorExamples':[0,1,2,3,4]})
    def test_large_report_fails_instead_of_silent_omission(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);self.seed(root);(root/'best-matches.html').write_text('x'*600000)
            with self.assertRaisesRegex(ValueError,'size limit'):collect(root)
    def test_identical_exports_are_noop(self):
        from private_reports import encoded
        files={'daily-evaluation.json':'{}'};manifest={'targetDate':'2026-10-18','sourceRunId':'1'}
        allfiles=files|{'checkpoint-manifest.json':encoded(manifest)}
        allfiles=allfiles|{"DATED/"+n:s for n,s in allfiles.items() if n in ['daily-evaluation.json','checkpoint-manifest.json']}
        entries=[]
        for n,s in allfiles.items():
            b=s.encode();entries.append({'path':('deney/reports/2026-10-18/'+n[6:]) if n.startswith('DATED/') else PREFIX+n,'sha':hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()})
        api=FakeApi(entries=entries);self.assertFalse(publish(api,files,manifest));self.assertEqual(api.writes,[])
    def test_owned_paths_only_and_one_atomic_ref_update(self):
        api=FakeApi(entries=[{'path':'futbol/futbol.html','sha':'keep'},{'path':PREFIX+'stability-evaluation.json','sha':'old'}])
        self.assertTrue(publish(api,{'daily-evaluation.json':'{}'},{'targetDate':'2026-10-18','sourceRunId':'1'}))
        updates=api.writes[0][2]['tree'];self.assertTrue(all(x['path'].startswith(PREFIX) or x['path'].startswith('deney/reports/2026-10-18/') for x in updates))
        self.assertTrue(any(x.get('sha','') is None for x in updates))
        self.assertEqual(sum(method=='PATCH' for _,method,_ in api.writes),1)

class RetentionTests(unittest.TestCase):
    def test_archive_removes_old_html_but_preserves_historical_evaluation(self):
        from datetime import date
        entries=[{'path':p,'type':'blob','sha':'old'} for p in ['raporlar/2026-10-16/x.html','raporlar/2026-10-17/x.html','deney/reports/2026-10-16/x.html','deney/reports/2026-10-16/stability-evaluation.json']]
        api=FakeApi(entries=entries)
        publish(api,{'daily-evaluation.json':'{}','futbol-yeni.html':'<body>new</body>'},{'targetDate':'2026-10-18','sourceRunId':'1'},date(2026,10,18))
        updates=api.writes[0][2]['tree'];deleted={x['path'] for x in updates if x.get('sha','') is None}
        self.assertEqual(deleted,{'raporlar/2026-10-16/x.html','deney/reports/2026-10-16/x.html'})
        self.assertTrue(any(x['path']=='raporlar/2026-10-18/futbol-yeni.html' and 'content' in x for x in updates))
    def test_old_recheck_does_not_recreate_expired_html_folder(self):
        from datetime import date
        api=FakeApi();publish(api,{'futbol-yeni.html':'old','daily-evaluation.json':'{}'},{'targetDate':'2026-10-16','sourceRunId':'1'},date(2026,10,18))
        paths={x['path'] for x in api.writes[0][2]['tree']}
        self.assertNotIn('raporlar/2026-10-16/futbol-yeni.html',paths)
        self.assertNotIn('deney/reports/2026-10-16/futbol-yeni.html',paths)
        self.assertIn('deney/reports/2026-10-16/daily-evaluation.json',paths)

if __name__=='__main__':unittest.main()

