"""Keep savings outside the production prediction and result-update paths."""
from pathlib import Path
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]


class ActionsStoragePolicyTests(unittest.TestCase):
    def workflow(self, name):
        # BaseLoader preserves the YAML key 'on' rather than treating it as bool.
        return yaml.load((ROOT / '.github/workflows' / name).read_text(), Loader=yaml.BaseLoader)

    def test_research_requires_explicit_manual_opt_in(self):
        wf = self.workflow('ensemble-market-validation.yml')
        option = wf['on']['workflow_dispatch']['inputs']['run_research']
        self.assertEqual(option['type'], 'boolean')
        self.assertEqual(option['default'], 'false')
        self.assertEqual(wf['jobs']['research']['if'], "github.event_name == 'workflow_dispatch' && inputs.run_research == true")
        self.assertNotIn('needs', wf['jobs']['primary'])

    def test_primary_checkpoint_and_immediate_publication_are_preserved(self):
        steps = self.workflow('ensemble-market-validation.yml')['jobs']['primary']['steps']
        upload = next(s for s in steps if s.get('id') == 'primary_checkpoint')
        self.assertEqual(upload['uses'], './.github/actions/private-upload')
        self.assertEqual(upload['with']['retention-days'], '7')
        self.assertIn('secrets.PRIVATE_ARTIFACT_KEY', upload['with']['key'])
        publish = next(s for s in steps if s.get('name') == 'Publish primary HTML immediately without waiting for research')
        self.assertIn('steps.primary_checkpoint.outputs.artifact-id', publish['env']['PRIMARY_ARTIFACT_ID'])
        self.assertLess(steps.index(upload), steps.index(publish))

    def test_control_does_not_start_the_legacy_coordinator(self):
        wf = self.workflow('parallel-experiment.yml')
        self.assertEqual(wf['on']['workflow_run']['workflows'], ['Daily Prediction'])
        self.assertIn('workflow_dispatch', wf['on'])


if __name__ == '__main__':
    unittest.main()
