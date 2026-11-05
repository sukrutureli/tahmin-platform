import unittest
from pathlib import Path
import yaml

class WorkflowSplitTests(unittest.TestCase):
    def test_primary_publishes_before_isolated_research(self):
        w=yaml.safe_load(Path('.github/workflows/ensemble-market-validation.yml').read_text());a=w['jobs']['primary'];b=w['jobs']['research']
        self.assertEqual(b['needs'],'primary')
        names=[s.get('name','') for s in a['steps']]
        self.assertLess(names.index('Save encrypted primary forecasts before background work'),names.index('Publish primary HTML immediately without waiting for research'))
        self.assertNotIn('Discover and freeze two-condition history rules (shadow only)',names)
        self.assertNotIn('Refresh today\'s finished football outcomes (artifact only)',names)
        self.assertIn('Discover and freeze two-condition history rules (shadow only)',[s.get('name') for s in b['steps']])
        checkpoint=next(s for s in b['steps'] if s.get('name')=='Restore exact primary checkpoint')
        self.assertEqual(checkpoint['with']['run-id'],'${{ github.run_id }}')
        self.assertTrue(all('steps.cfg.outputs' not in str(s) for s in b['steps']))
        self.assertIn('Restore reference and optional bootstrap from primary checkpoint',[s.get('name') for s in b['steps']])
