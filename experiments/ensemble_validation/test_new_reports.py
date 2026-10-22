import hashlib,json,tempfile,unittest
from pathlib import Path
from new_reports import reports

class NewReportTests(unittest.TestCase):
    def test_two_sports_and_results_are_rendered_without_changing_any_frozen_source(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);model={'protocol':{'version':'opponent-locked-v1','first_forecast_date':'2026-10-19'},'payload':{'footballDistribution':{'dispersion':None,'rho':0},'basketballCovariance':[[100,0],[0,100]]}}
            (root/'stability-model.json').write_text(json.dumps(model));digest=hashlib.sha256((root/'stability-model.json').read_bytes()).hexdigest()
            systems={}
            for sport,score in [('football',[1,0]),('basketball',[80,70])]:
                entry={'sport':sport,'date':'2026-10-19','eventId':'42','name':sport+' Home - Away','time':'20:00','prospectiveBeforeKickoff':True,'score':score,'scoreMean':score,'markets':{'MS':[.7,.2,.1] if sport=='football' else [.7,.3]},'chosen':{'market':'MS','option':0,'confidence':.7}}
                systems[sport]={'opponent-locked-v1':[entry]}
                (root/(sport+'-replay.json')).write_text(json.dumps([{'date':'2026-10-19','eventId':'42','realScore':'-'.join(map(str,score)),'odds':{'ms1':1.8,'mbs':2}}]))
            (root/'stability-before-results.json').write_text(json.dumps({'targetDate':'2026-10-19','version':'opponent-locked-v1','modelSha256':digest,'systems':systems,'createdAt':'2026-10-18T22:00:00Z'}))
            before={p.name:p.read_bytes() for p in root.iterdir()}
            manifest=reports(root)
            self.assertFalse(manifest['previewOnly']);self.assertEqual(manifest['reports']['futbol']['fixtureCount'],1)
            for folder,sport in [('futbol','football'),('basketbol','basketball')]:
                s=(root/(folder+'-yeni.html')).read_text();self.assertIn(sport+' Home',s);self.assertIn('Oran <b>1.80</b>',s);self.assertIn('MBS <b>2</b>',s);self.assertIn('Kazandı',s);self.assertIn('id="min-odds"',s);self.assertIn('data-odds="1.8"',s)
                self.assertIn('id="match-search"',s);self.assertIn('data-search="'+sport+' Home - Away"',s)
            self.assertEqual(before,{n:(root/n).read_bytes() for n in before})
    def test_later_day_cannot_use_unlocked_research_forecasts(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);(root/'context-before-results.json').write_text('{"targetDate":"2026-10-19"}')
            with self.assertRaisesRegex(ValueError,'Missing locked'):reports(root)

if __name__=='__main__':unittest.main()

class FilterTests(unittest.TestCase):
    def test_odds_finished_and_clock_filters_work_together(self):
        import subprocess
        from new_reports import FILTER_SCRIPT
        script=FILTER_SCRIPT.replace('<script>','').replace('</script>','')
        harness="""
import vm from 'node:vm';import assert from 'node:assert/strict';
const input={value:'',addEventListener(t,f){this.run=f}},finished={checked:false,addEventListener(t,f){this.run=f}},started={checked:false,addEventListener(t,f){this.run=f}},clear={addEventListener(t,f){this.run=f}},count={};
const search={value:'',addEventListener(t,f){this.run=f}};
const rows=[
{dataset:{odds:'1.8',finished:'1',kickoff:'2026-10-18T13:00:00+03:00'}},
{dataset:{odds:'1.8',finished:'0',kickoff:'2026-10-18T14:00:00+03:00'}},
{dataset:{odds:'1.4',finished:'0',kickoff:'2026-10-18T15:00:00+03:00'}},
{dataset:{odds:'2.0',finished:'0',kickoff:'2026-10-18T15:00:00+03:00'}},
{dataset:{odds:'1.9',finished:'0',kickoff:''}}];let clock=Date.parse('2026-10-18T11:00:00Z'),timer;
const ctx={Date:class extends Date{static now(){return clock}},Number,document:{getElementById:id=>({'min-odds':input,'hide-finished':finished,'hide-started':started,'clear-odds':clear,'filter-count':count}[id]),querySelectorAll:()=>rows},window:{addEventListener(){}},setInterval(f){timer=f}};
rows.forEach((r,i)=>r.dataset.search=['İstanbul - Beşiktaş','IĞDIR - Şanlıurfa','Fenerbahçe - İzmir','Beşiktaş - İstanbul','Other - Away'][i]);
const originalGet=ctx.document.getElementById;ctx.document.getElementById=id=>id==='match-search'?search:originalGet(id);
vm.runInNewContext(SCRIPT,ctx);
search.value='istanbul BESIKTAS';search.run();assert.deepEqual(rows.map(r=>r.hidden),[false,true,true,false,true]);
input.value='1.9';input.run();assert.deepEqual(rows.map(r=>r.hidden),[true,true,true,false,true]);assert.equal(count.textContent,'1 / 5 maç');
search.value='ığdır';search.run();assert.ok(rows.every(r=>r.hidden));
input.value='';input.run();assert.deepEqual(rows.map(r=>r.hidden),[true,false,true,true,true]);
search.value='nonexistent';search.run();assert.equal(count.textContent,'0 / 5 maç');
clear.run();assert.equal(search.value,'');assert.ok(rows.every(r=>!r.hidden));
finished.checked=true;finished.run();assert.deepEqual(rows.map(r=>r.hidden),[true,false,false,false,false]);
started.checked=true;started.run();assert.deepEqual(rows.map(r=>r.hidden),[true,true,false,false,false]);
input.value='1.50';input.run();assert.deepEqual(rows.map(r=>r.hidden),[true,true,true,false,false]);assert.equal(count.textContent,'2 / 5 maç');
clock=Date.parse('2026-10-18T12:00:00Z');timer();assert.deepEqual(rows.map(r=>r.hidden),[true,true,true,true,false]);
clear.run();assert.ok(rows.every(r=>!r.hidden));assert.equal(finished.checked,false);assert.equal(started.checked,false);
""".replace('SCRIPT',json.dumps(script))
        subprocess.run(['node','--input-type=module'],input=harness,text=True,check=True,capture_output=True)
