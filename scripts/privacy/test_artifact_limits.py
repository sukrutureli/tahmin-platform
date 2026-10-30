import base64,os,tempfile,unittest,zipfile,io
from pathlib import Path
from unittest.mock import patch
import artifact
class ArtifactLimitsTests(unittest.TestCase):
 def test_separate_expanded_and_compressed_limits_and_authentication(self):
  with tempfile.TemporaryDirectory() as d, patch.dict(os.environ,{'PRIVATE_ARTIFACT_KEY':base64.b64encode(b'x'*32).decode()}):
   p=Path(d);src=p/'src';src.mkdir();(src/'data').write_bytes(b'A'*20000)
   with patch.object(artifact,'LIMIT',1000),patch.object(artifact,'EXPANDED_LIMIT',30000):
    artifact.pack(src,p/'enc');artifact.unpack(p/'enc',p/'dst');self.assertEqual((p/'dst/data').read_bytes(),b'A'*20000)
   with patch.object(artifact,'EXPANDED_LIMIT',10000):
    with self.assertRaises(ValueError):artifact.pack(src,p/'reject')
    with self.assertRaises(ValueError):artifact.unpack(p/'enc',p/'reject-dir')
   data=bytearray((p/'enc').read_bytes());data[-1]^=1;(p/'tamper').write_bytes(data)
   with self.assertRaises(Exception):artifact.unpack(p/'tamper',p/'bad')
   self.assertFalse((p/'bad').exists())
 def test_symlink_still_rejected(self):
  with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'PRIVATE_ARTIFACT_KEY':base64.b64encode(b'x'*32).decode()}):
   p=Path(d);src=p/'src';src.mkdir();(p/'secret').write_text('test');(src/'link').symlink_to(p/'secret')
   with self.assertRaises(ValueError):artifact.pack(src,p/'enc')
