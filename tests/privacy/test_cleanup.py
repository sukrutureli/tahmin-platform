import base64
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/privacy'))
import artifact
import cleanup_public_outputs as cleanup

class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.env=patch.dict(os.environ,PRIVATE_ARTIFACT_KEY=base64.b64encode(b'x'*32).decode(),GITHUB_RUN_ID='123',BATCH_NUMBER='0');self.env.start()
        self.item={'kind':'artifact','id':4,'run':5,'name':'synthetic','created':'2026-10-17T00:00:00Z','size':100}
    def tearDown(self):self.env.stop();self.tmp.cleanup()
    def test_cutoff_and_protected_runs(self):
        self.assertTrue(cleanup.eligible({'id':1,'created_at':'2026-10-17T00:00:00Z'}))
        self.assertFalse(cleanup.eligible({'id':1,'created_at':cleanup.CUTOFF}))
        self.assertFalse(cleanup.eligible({'id':39084079657,'created_at':'2026-10-17T00:00:00Z'}))
        for item in [{**self.item,'created':cleanup.CUTOFF},{**self.item,'run':39084004424}]:
            with self.assertRaises(ValueError):cleanup.validate_item(item)
    def test_batches_bounded_and_order_preserved(self):
        items=[{**self.item,'id':i,'size':3} for i in range(7)]
        result=cleanup.make_batches(items,maximum=3,byte_limit=8)
        self.assertEqual([len(x['items']) for x in result],[2,2,2,1])
        self.assertEqual([x['id'] for b in result for x in b['items']],list(range(7)))
    def fake_source(self):
        p=self.root/'original.zip'
        with zipfile.ZipFile(p,'w') as z:z.writestr('private.json','{"synthetic_secret":true}')
        return p
    def backup(self):
        source=self.fake_source()
        class Fake:
            def download(self,path,target):target.write_bytes(source.read_bytes());return True
        root=self.root/'backup';cleanup.backup(Fake(),[self.item],root);return root
    def test_backup_contains_ciphertext_and_recovers_original_zip(self):
        root=self.backup();cipher=root/'artifact-4.enc'
        self.assertNotIn(b'synthetic_secret',cipher.read_bytes())
        artifact.unpack(cipher,self.root/'manual')
        self.assertEqual((self.root/'original.zip').read_bytes(),(self.root/'manual/archive.zip').read_bytes())
        self.assertFalse(list(self.root.glob('stage-*')))
    def remote(self,root,corrupt=False,name=None):
        out=self.root/'remote.zip'
        with zipfile.ZipFile(out,'w') as z:
            for p in root.iterdir():z.writestr(p.name,b'corrupt' if corrupt and p.suffix=='.enc' else p.read_bytes())
        deleted=[]
        class Fake:
            def json(self,path):return {'name':name or 'private-backup-123-0','expired':False,'workflow_run':{'id':123}}
            def download(self,path,target):target.write_bytes(out.read_bytes());return True
            def request(self,path,method,missing_ok):deleted.append((path,method))
        return Fake(),deleted
    def test_no_delete_without_matching_remote_backup(self):
        root=self.backup();api,deleted=self.remote(root,name='wrong')
        with self.assertRaises(RuntimeError):cleanup.delete_after_remote_verification(api,root,9)
        self.assertEqual(deleted,[])
    def test_no_delete_if_uploaded_ciphertext_changed(self):
        root=self.backup();api,deleted=self.remote(root,corrupt=True)
        with self.assertRaises(RuntimeError):cleanup.delete_after_remote_verification(api,root,9)
        self.assertEqual(deleted,[])
    def test_delete_only_after_remote_bytes_verified(self):
        root=self.backup();api,deleted=self.remote(root)
        cleanup.delete_after_remote_verification(api,root,9)
        self.assertEqual(deleted,[('actions/artifacts/4','DELETE')])
    def test_missing_key_blocks_backup_before_source_fetch(self):
        os.environ['PRIVATE_ARTIFACT_KEY']=''
        class Fake:
            def download(self,*args):raise AssertionError('No source fetch should happen')
        with self.assertRaises(ValueError):cleanup.backup(Fake(),[self.item],self.root/'backup')
    def test_already_absent_source_never_deleted(self):
        class Fake:
            def download(self,*args):return False
        root=self.root/'backup';cleanup.backup(Fake(),[self.item],root)
        api,deleted=self.remote(root);cleanup.delete_after_remote_verification(api,root,9)
        self.assertEqual(deleted,[])

if __name__=='__main__':unittest.main()
