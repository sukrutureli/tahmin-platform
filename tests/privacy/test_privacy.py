import base64
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
import zipfile
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ROOT = Path(__file__).resolve().parents[2]
def module(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts/privacy'/f'{name}.py')
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result
artifact=module('artifact'); workflow=module('prepare_workflows'); panel=module('build_panel'); access=module('verify_access')

class PrivacyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.env=patch.dict(os.environ,PRIVATE_ARTIFACT_KEY=base64.b64encode(b'x'*32).decode());self.env.start()
    def tearDown(self):
        self.env.stop();self.tmp.cleanup()
    def sample(self):
        source=self.root/'source';source.mkdir();(source/'data').mkdir()
        (source/'data'/'forecast.json').write_bytes(b'{"private":"secret-match"}')
        (source/'index.html').write_text('<h1>secret-match</h1>')
        return source
    def test_roundtrip_and_no_plaintext(self):
        source=self.sample();packed=self.root/'payload.enc';artifact.pack(source,packed)
        self.assertNotIn(b'secret-match',packed.read_bytes())
        artifact.unpack(packed,self.root/'restored')
        for path in source.rglob('*'):
            if path.is_file():self.assertEqual(path.read_bytes(),(self.root/'restored'/path.relative_to(source)).read_bytes())
    def test_expanded_size_is_limited_before_encryption(self):
        source=self.sample()
        with patch.object(artifact,'LIMIT',10):
            with self.assertRaises(ValueError):artifact.pack(source,self.root/'out')
        self.assertFalse((self.root/'out').exists())
    def test_missing_key_fails_without_output(self):
        os.environ['PRIVATE_ARTIFACT_KEY']=''
        with self.assertRaises(ValueError):artifact.pack(self.sample(),self.root/'out')
        self.assertFalse((self.root/'out').exists())
    def test_tampering_and_wrong_key_do_not_extract(self):
        packed=self.root/'payload';artifact.pack(self.sample(),packed);data=packed.read_bytes()
        for mode in ('tamper','key'):
            packed.write_bytes(data[:-1]+bytes([data[-1]^1]) if mode=='tamper' else data)
            if mode=='key':os.environ['PRIVATE_ARTIFACT_KEY']=base64.b64encode(b'y'*32).decode()
            with self.assertRaises(Exception):artifact.unpack(packed,self.root/'restored')
            self.assertFalse((self.root/'restored').exists())
    def test_plain_artifacts_rejected(self):
        p=self.root/'legacy';p.write_bytes(b'PK legacy plaintext')
        with self.assertRaises(ValueError):artifact.unpack(p,self.root/'restored')
    def test_unsafe_encrypted_archive_rejected(self):
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,'w') as z:z.writestr('ok','safe');z.writestr('../escape','secret')
        nonce=b'1'*12;p=self.root/'payload'
        p.write_bytes(artifact.MAGIC+nonce+AESGCM(b'x'*32).encrypt(nonce,buf.getvalue(),artifact.MAGIC))
        with self.assertRaises(ValueError):artifact.unpack(p,self.root/'restored')
        self.assertFalse((self.root/'restored').exists())
    def test_symlinks_rejected(self):
        source=self.sample();(source/'link').symlink_to(source/'index.html')
        with self.assertRaises(ValueError):artifact.pack(source,self.root/'out')
    def test_logs_hidden_on_failure_and_success(self):
        for command,code in [('echo TOPSECRET',0),('echo TOPSECRET >&2; exit 7',7)]:
            result=subprocess.run([sys.executable,str(ROOT/'scripts/privacy/run_private.py')],input=command,
                  text=True,capture_output=True,env={**os.environ,'RUNNER_TEMP':str(self.root)})
            self.assertEqual(result.returncode,code);self.assertNotIn('TOPSECRET',result.stdout+result.stderr)
        self.assertTrue(any('TOPSECRET' in p.read_text() for p in self.root.rglob('*.log')))
    def test_prepared_workflows_have_only_encrypted_transport(self):
        for p in [ROOT/'.github/workflows/daily.yml',ROOT/'.github/workflows/control.yml',ROOT/'docs/migration/ensemble-market-validation.yml']:
            data=workflow.yaml.load(p.read_text(),Loader=workflow.Loader)
            self.assertIn('workflow_dispatch',data['on'])
            for job in data['jobs'].values():
                self.assertTrue(any(s.get('name')=='Require private artifact key' for s in job['steps']))
                for step in job['steps']:
                    self.assertNotIn(step.get('uses','').split('@')[0],('actions/upload-artifact','actions/download-artifact'))
                    if step.get('with',{}).get('repository')=='sukrutureli/fathertahmin':
                        self.assertEqual(step['with']['token'],workflow.READ)
    def test_panel_exports_only_reports(self):
        source=self.root/'published'
        for sport in ('futbol','basketbol'):
            (source/sport/'data').mkdir(parents=True)
            (source/sport/(sport+'.html')).write_text('<html>report</html>')
            (source/sport/'data'/'private.json').write_text('secret')
        output=self.root/'site';panel.build(source,output)
        self.assertFalse(list(output.rglob('*.json')))
        self.assertEqual((output/'futbol/index.html').read_text(),'<html>report</html>')
    def test_panel_missing_report_and_dirty_output_rejected(self):
        with self.assertRaises(ValueError):panel.build(self.root,self.root/'site')
        output=self.root/'site';output.mkdir();(output/'leak.json').write_text('x')
        with self.assertRaises(ValueError):panel.build(self.root,output)
    def test_gate_rejects_public_200_and_plain_403(self):
        for code,headers in [(200,{}),(403,{}),(302,{'Location':'https://evil.example/cdn-cgi/access/login'})]:
            response=type('Response',(),{'code':code,'headers':headers})()
            opener=type('Opener',(),{'open':lambda *a,**k:response})()
            with patch.object(access.urllib.request,'build_opener',return_value=opener):
                with self.assertRaises(ValueError):access.check('https://example.pages.dev')
    def test_gate_accepts_access_login_for_every_path(self):
        response=type('Response',(),{'code':302,'headers':{'Location':'https://team.cloudflareaccess.com/cdn-cgi/access/login/example'}})()
        calls=[]
        class Opener:
            def open(self,url,**kwargs):calls.append(url);return response
        with patch.object(access.urllib.request,'build_opener',return_value=Opener()):
            self.assertTrue(access.check('https://example.pages.dev'))
        self.assertEqual(len(calls),4)

if __name__=='__main__':unittest.main()
