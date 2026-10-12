import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from outcome_learning import features,fit_transform,transform_values,fit_classifier,softmax,learn,freeze,settle

class OutcomeLearningTests(unittest.TestCase):
    def test_saved_odds_and_history_features_ignore_labels_and_main(self):
        h=[{'date':'2026-10-09','venue':'home','for':2,'against':0,'win':1}]*6
        a=[{'date':'2026-10-08','venue':'away','for':0,'against':1,'win':0}]*6
        r={'date':'2026-10-11','realScore':'2-0','odds':{'ms1':2,'msX':3,'ms2':4},'variants':{'six-simple':{'audit':{'home':{'rows':h},'away':{'rows':a}}}}}
        before=features(r,'football');r['realScore']='0-9';r['published']={'pHome':0}
        self.assertEqual(before,features(r,'football'))
        self.assertAlmostEqual(before['marketHome'],(1/2)/(1/2+1/3+1/4))

    def test_preprocessing_fits_train_only_and_missing_inputs_stay_finite(self):
        t,x=fit_transform([{'a':1},{'a':3},{}],['a','absent']);saved=copy.deepcopy(t)
        y=transform_values([{'a':10000},{}],t)
        self.assertEqual(t,saved);self.assertTrue(np.isfinite(y).all());self.assertEqual(t['median'],[2,0])

    def dataset(self):
        rows=[]
        for date,n in [('2026-10-01',50),('2026-10-02',50),('2026-10-10',20),('2026-10-11',20),('2026-10-12',20)]:
            for v in [-1,1]:
                for i in range(n):rows.append({'date':date,'eventId':str(v)+str(i),'name':'A - B','realScore':'90-80' if v>0 else '80-90',
                    'f':{'attackDefenceDiff':v,'marketHome':.8 if v>0 else .2},'variants':{'legacy':{'models':{'BasketEnsembleModel':{'pHome':.4,'pAway':.6,'pOver25':.5,'scoreline':'81-80'}}}}})
        return rows

    def test_test_labels_and_main_cannot_select_or_change_learned_model(self):
        rows=self.dataset()
        with patch('outcome_learning.features',side_effect=lambda r,s:r['f']):
            a=learn(rows,'basketball','MS','2026-10-12')
            changed=copy.deepcopy(rows)
            for r in changed:
                r['variants']['legacy']['models']['BasketEnsembleModel']['pHome']=.99
                r['variants']['legacy']['models']['BasketEnsembleModel']['pAway']=.01
                if r['date']>='2026-10-11':r['realScore']='90-80'
            b=learn(changed,'basketball','MS','2026-10-12')
        self.assertEqual(a['model'],b['model']);self.assertGreater(a['test']['learned']['accuracy'],b['test']['learned']['accuracy'])

    def test_probabilities_are_normalized(self):
        x=np.column_stack([np.ones(100),np.linspace(-2,2,100)]);y=(x[:,1]>0).astype(int)
        w=fit_classifier(x,y,2,1);p=softmax(x@w)
        self.assertTrue(np.isfinite(p).all());self.assertTrue(np.allclose(p.sum(axis=1),1));self.assertGreater((p.argmax(axis=1)==y).mean(),.95)

    def test_learned_forecast_and_score_are_saved_and_reused_unchanged(self):
        rows=self.dataset();row=copy.deepcopy(rows[-1]);row['time']='23:59';row['realScore']='LIVE 90-80';row['odds']={'hOverUnderValue':165}
        t,x=fit_transform([{'marketHome':.2},{'marketHome':.8}],['marketHome'])
        classifier={'mode':'odds','transform':t,'weights':[[0,0],[2,-2],[0,0]],'penalty':1}
        score={'mode':'odds','transform':t,'weights':[[82,80],[0,0],[0,0]],'penalty':1}
        report={'targetDate':row['date'],'models':[{'sport':'basketball','market':'MS','model':classifier},
                {'sport':'basketball','market':'OU','model':None},{'sport':'basketball','market':'score','model':score}]}
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);a=root/'a';b=root/'b';a.mkdir();b.mkdir()
            with patch('outcome_learning.features',side_effect=lambda r,s:r['f']):
                freeze(a,{'basketball':[row]},report);saved=(a/'learned-before-results.json').read_bytes()
                self.assertEqual(json.loads(saved)['predictions'][0]['score'],[82,80])
                classifier['weights'][0]=[-10,10];freeze(b,{'basketball':[row]},report,a)
            self.assertEqual(saved,(b/'learned-before-results.json').read_bytes())
            settle(b,{'basketball':[row]},row['date'])
            e=json.loads((b/'learned-daily-evaluation.json').read_text());ms=next(x for x in e['markets'] if x['sport']=='basketball' and x['market']=='MS')
            self.assertIsNone(ms['all']['learned'])
            row['realScore']='90-80';settle(b,{'basketball':[row]},row['date'])
            e=json.loads((b/'learned-daily-evaluation.json').read_text());ms=next(x for x in e['markets'] if x['sport']=='basketball' and x['market']=='MS')
            self.assertEqual(ms['all']['learned']['accuracy'],1)
            self.assertEqual(ms['all']['main']['accuracy'],0)
