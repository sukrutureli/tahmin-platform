import ast,json,subprocess,unittest
from pathlib import Path
SOURCE=Path(__file__).with_name('new_reports.py')
def filter_script():
 tree=ast.parse(SOURCE.read_text())
 return next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='FILTER_SCRIPT' for t in n.targets)).replace('<script>','').replace('</script>','')
class FilterSummaryTests(unittest.TestCase):
 def test_visible_results_multi_select_rank_pending_reset_and_empty(self):
  harness=r"""
import vm from 'node:vm';import assert from 'node:assert/strict';
function element(){return {value:'',checked:false,children:[],addEventListener(t,f){this.run=f},appendChild(x){this.children.push(x)},querySelectorAll(selector){const all=this.children.flatMap(x=>x.type==='checkbox'?[x]:x.children||[]).filter(x=>x.type==='checkbox');return selector==='input:checked'?all.filter(x=>x.checked):all}}}
const input=element(),search=element(),mbs=element(),pick=element(),finished=element(),started=element(),clear=element(),count={},summary={};
for(const value of ['1','2','3'])mbs.appendChild({...element(),type:'checkbox',value});
const rows=[
{dataset:{outcome:'won',mbs:'1',pick:'MS1',odds:'1.8',finished:'1',search:'Home A',rank:'1',eligible:'5'}},
{dataset:{outcome:'lost',mbs:'2',pick:'Üst',odds:'1.9',finished:'1',search:'Home B',rank:'2',eligible:'5'}},
{dataset:{outcome:'won',mbs:'2',pick:'Alt',odds:'1.5',finished:'1',search:'Home C',rank:'3',eligible:'5'}},
{dataset:{outcome:'pending',mbs:'3',pick:'MS1',odds:'2.0',finished:'0',search:'Home D',rank:'4',eligible:'5'}},
{dataset:{outcome:'unverified',mbs:'3',pick:'KG Var',odds:'1.7',finished:'1',search:'Home E',rank:'5',eligible:'5'}},
{dataset:{outcome:'no-choice',mbs:'',pick:'',odds:'0',finished:'0',search:'Other',rank:'0',eligible:'5'}}];
const nodes={'min-odds':input,'match-search':search,'mbs-filter':mbs,'pick-filter':pick,'hide-finished':finished,'hide-started':started,'clear-odds':clear,'filter-count':count,'filtered-summary':summary};
const rankings=['0.25','0.5','0.75','1'].map(value=>({value,checked:value==='1',addEventListener(t,f){this.run=f}})),ranking=rankings[1];
const ctx={Date,Number,document:{createElement:element,createTextNode:text=>({text}),getElementById:id=>nodes[id],querySelector:()=>rankings.find(r=>r.checked),querySelectorAll:selector=>selector==='[name=rank-filter]'?rankings:rows},window:{addEventListener(){}},setInterval(){}};
vm.runInNewContext(SCRIPT,ctx);
const choose=(group,values)=>{group.querySelectorAll('input').forEach(b=>b.checked=values.includes(b.value));group.run()};
assert.equal(summary.textContent,'Filtrelenen: 6 maç · 3 sonuçlandı · 2 tuttu · 1 yattı · 1 bekliyor · 1 iade / doğrulanmadı · 1 tercih yok · İsabet %66,7');
choose(mbs,['2','3']);
assert.equal(summary.textContent,'Filtrelenen: 4 maç · 2 sonuçlandı · 1 tuttu · 1 yattı · 1 bekliyor · 1 iade / doğrulanmadı · İsabet %50');
choose(pick,['MS1','Üst']);
assert.equal(summary.textContent,'Filtrelenen: 2 maç · 1 sonuçlandı · 0 tuttu · 1 yattı · 1 bekliyor · İsabet %0');
clear.run();rankings.forEach(r=>r.checked=r===ranking);ranking.run();
assert.equal(summary.textContent,'Filtrelenen: 3 maç · 3 sonuçlandı · 2 tuttu · 1 yattı · 0 bekliyor · İsabet %66,7');
clear.run();finished.checked=true;finished.run();
assert.equal(summary.textContent,'Filtrelenen: 2 maç · 0 sonuçlandı · 0 tuttu · 0 yattı · 1 bekliyor · 1 tercih yok · İsabet —');
search.value='nonexistent';search.run();
assert.equal(summary.textContent,'Filtrelenen: 0 maç · 0 sonuçlandı · 0 tuttu · 0 yattı · 0 bekliyor · İsabet —');
clear.run();input.value='2.0';input.run();
assert.equal(summary.textContent,'Filtrelenen: 1 maç · 0 sonuçlandı · 0 tuttu · 0 yattı · 1 bekliyor · İsabet —');
clear.run();assert.equal(count.textContent,'6 / 6 maç');assert.ok(summary.textContent.includes('2 tuttu · 1 yattı'));
""".replace('SCRIPT',json.dumps(filter_script()))
  completed=subprocess.run(['node','--input-type=module'],input=harness,text=True,capture_output=True)
  self.assertEqual(completed.returncode,0,completed.stderr)
if __name__=='__main__':unittest.main()

