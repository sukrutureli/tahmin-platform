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
for(const min of [1.5,1.7,1.8,null]){const show=filterChoices(row,min,[]);out.push([show,tiles.map(t=>!t.hidden),choiceViews.get(row).visibleOutcome,cell.innerHTML]);}
filterChoices(row,null,['KG Yok']);out.push([choiceViews.get(row).visibleOutcome,tiles.map(t=>!t.hidden)]);
console.log(JSON.stringify(out));
'''
        out=json.loads(subprocess.run(['node','-e',harness],text=True,capture_output=True,check=True).stdout)
        self.assertEqual(out[0][:3],[True,[True,True],'partial'])
        self.assertEqual(out[1][:3],[True,[True,True],'won'])
        self.assertNotIn('KG Yok',out[1][3])
        self.assertEqual(out[2][:3],[False,[True,True],'no-choice'])
        self.assertEqual(out[3][:3],[True,[True,True],'partial'])
        self.assertEqual(out[4],['lost',[True,True]])

    def test_no_mutation_of_frozen_markup_and_idempotence(self):
        doc='<style></style><tr data-match-outcome="partial">unchanged</tr><script>function updateSummary(){return row.dataset.matchOutcome||\'pending\';}function filter(){const below=min!==null&&Number.isFinite(min)&&!(odd>1&&odd>=min);}</script>'
        upgraded=upgrade_rule_html(doc)
        self.assertIn('<tr data-match-outcome="partial">unchanged</tr>',upgraded)
        self.assertIn('below=!filterChoices(row,min,pickValues)',upgraded)
        self.assertEqual(upgraded,upgrade_rule_html(upgraded))
        self.assertEqual(upgrade_rule_html('<html>legacy</html>'),'<html>legacy</html>')

    def test_600_rows_repeat_filter_has_no_dom_writes(self):
        harness=r"""
let writes=0,creates=0;
function cell(initial){let value=initial;return {get innerHTML(){return value;},set innerHTML(v){writes++;value=v;},appendChild(){writes++;}};}
function row(){const status=cell('Alt: ✅ Tuttu<br>KG Yok: ❌ Yattı'),meta=cell('original');const tiles=[['Alt','1.77'],['KG Yok','1.56']].map(([caption,price])=>({querySelector:s=>({textContent:s==='small'?price:caption})}));return {dataset:{picks:'["Alt","KG Yok"]'},querySelectorAll:()=>tiles,querySelector:s=>s==='.bet-meta'?meta:status};}
const rows=Array.from({length:600},row),document={createElement:()=>{creates++;return {style:{}};}};
"""+CHOICE_SCRIPT+r"""
for(let i=0;i<20;i++)for(const row of rows)filterChoices(row,null,[]);
const unchanged=[writes,creates];
for(const row of rows)filterChoices(row,1.7,[]);
const once=[writes,creates];
for(let i=0;i<20;i++)for(const row of rows)filterChoices(row,1.7,[]);
const repeated=[writes,creates];
for(const row of rows)filterChoices(row,1.8,[]);
console.log(JSON.stringify({unchanged,once,repeated,excluded:[writes,creates]}));
"""
        result=json.loads(subprocess.run(['node','-e',harness],text=True,capture_output=True,check=True).stdout)
        self.assertEqual(result['unchanged'],[0,0])
        self.assertGreater(result['once'][0],0)
        self.assertEqual(result['repeated'],result['once'])
        self.assertEqual(result['excluded'],result['once'])

    def test_existing_published_script_is_upgraded_and_frame_coalesced(self):
        doc='<style></style><tr data-match-outcome="partial">unchanged</tr><script>function updateSummary(){return row.dataset.visibleMatchOutcome||row.dataset.matchOutcome||\'pending\';}const choiceViews=new Map();oldHelper();function filter(){row.hidden=below;if(!row.hidden)n++;}input.addEventListener(\'input\',filter);setInterval(filter,30000);</script>'
        changed=upgrade_rule_html(doc)
        self.assertNotIn('oldHelper()',changed)
        self.assertIn('requestAnimationFrame',changed)
        self.assertIn("addEventListener('input',queueFilter)",changed)
        self.assertIn('if(row.hidden!==hide)',changed)
        self.assertEqual(changed,upgrade_rule_html(changed))
