import json,subprocess,unittest
from selection_filter import CHOICE_SCRIPT,upgrade_rule_html

class SelectionFilterTests(unittest.TestCase):
    def test_each_price_and_visible_match_result(self):
        harness=r'''
const makeTile=(caption,price)=>({hidden:false,querySelector:s=>({textContent:s==='small'?price:caption})});
const tiles=[makeTile('2.5 Alt','1.77'),makeTile('KG Yok','1.56')];
const cell={innerHTML:'Alt: ✅ Tuttu<br>KG Yok: ❌ Yattı'};
const meta={innerHTML:'old',appendChild(){}};
const row={dataset:{picks:'["Alt","KG Yok"]',mbs:'3'},querySelectorAll:()=>tiles,querySelector:s=>s==='.bet-meta'?meta:cell};
const rows=[row],document={createElement:()=>({style:{}})};
'''+CHOICE_SCRIPT+r'''
const out=[];
for(const min of [1.5,1.7,1.8,null]){const show=filterChoices(row,min,[]);out.push([show,tiles.map(t=>!t.hidden),row.dataset.visibleMatchOutcome,cell.innerHTML]);}
filterChoices(row,null,['KG Yok']);out.push([row.dataset.visibleMatchOutcome,tiles.map(t=>!t.hidden)]);
console.log(JSON.stringify(out));
'''
        out=json.loads(subprocess.run(['node','-e',harness],text=True,capture_output=True,check=True).stdout)
        self.assertEqual(out[0][:3],[True,[True,True],'partial'])
        self.assertEqual(out[1][:3],[True,[True,False],'won'])
        self.assertNotIn('KG Yok',out[1][3])
        self.assertEqual(out[2][:3],[False,[False,False],'no-choice'])
        self.assertEqual(out[3][:3],[True,[True,True],'partial'])
        self.assertEqual(out[4],['lost',[False,True]])

    def test_no_mutation_of_frozen_markup_and_idempotence(self):
        doc='<style></style><tr data-match-outcome="partial">unchanged</tr><script>function updateSummary(){return row.dataset.matchOutcome||\'pending\';}function filter(){const below=min!==null&&Number.isFinite(min)&&!(odd>1&&odd>=min);}</script>'
        upgraded=upgrade_rule_html(doc)
        self.assertIn('<tr data-match-outcome="partial">unchanged</tr>',upgraded)
        self.assertIn('below=!filterChoices(row,min,pickValues)',upgraded)
        self.assertEqual(upgraded,upgrade_rule_html(upgraded))
        self.assertEqual(upgrade_rule_html('<html>legacy</html>'),'<html>legacy</html>')
