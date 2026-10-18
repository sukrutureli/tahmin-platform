import unittest
from display_odds import display_values,enrich_rows

class DisplayOddsTests(unittest.TestCase):
    def test_every_market_uses_selected_option_price(self):
        keys={'ms1':1.1,'msX':2.2,'ms2':3.3,'over25':1.4,'under25':1.5,'bttsYes':1.6,'bttsNo':1.7,'mbs':3}
        row={'sport':'football','odds':keys}
        for market,prices in [('MS',['1.10','2.20','3.30']),('OU',['1.40','1.50']),('BTTS',['1.60','1.70'])]:
            for i,price in enumerate(prices):self.assertEqual(display_values(row,market,i),(price,'3'))
        row={'sport':'basketball','odds':{'ms1':1.8,'ms2':2.1,'over':1.7,'under':1.9}}
        self.assertEqual(display_values(row,'MS',1),('2.10','—'))
        self.assertEqual(display_values(row,'OU',1),('1.90','—'))
    def test_invalid_or_missing_values_are_never_invented(self):
        for bad in [None,0,1,float('nan'),float('inf'),True]:
            self.assertEqual(display_values({'sport':'football','odds':{'ms1':bad,'mbs':0}},'MS',0),('—','—'))
    def test_order_is_verified_and_fixture_id_is_attached(self):
        e={'sport':'football','date':'2026-10-18','eventId':'42','name':'A - B','market':'MS','optionIndex':1}
        body='<tr><td>A - B</td></tr>';bank={('football',e['date'],'42'):{'sport':'football','odds':{'msX':3.4,'mbs':2}}}
        rendered=enrich_rows(body,[e],bank,0)
        self.assertIn('data-event-id="42"',rendered);self.assertIn('3.40',rendered);self.assertIn('MBS <b>2</b>',rendered)
        self.assertEqual(enrich_rows(rendered,[e],bank,0),rendered)
        with self.assertRaises(ValueError):enrich_rows(body,[dict(e,name='Other')],bank,0)

if __name__=='__main__':unittest.main()
