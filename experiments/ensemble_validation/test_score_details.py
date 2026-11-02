import unittest
from score_details import football_score,compatible
class ScoreDetails(unittest.TestCase):
    def test_detail_preserves_mode_and_has_unconditional_probabilities(self):
        model={'rho':0,'dispersion':None}
        for market,option in [('BTTS',0),('BTTS',1),('OU',0),('OU',1),('MS',0),('MS',1),('MS',2)]:
            original=football_score([1.6,1.3],model,market,option)
            detail=football_score([1.6,1.3],model,market,option,top_n=3)
            self.assertEqual(original['score'],detail['score'])
            self.assertEqual(detail['score'],detail['topScores'][0]['score'])
            self.assertEqual(len(detail['topScores']),3)
            probabilities=[s['probability'] for s in detail['topScores']]
            self.assertEqual(probabilities,sorted(probabilities,reverse=True))
            self.assertTrue(0<sum(probabilities)<1)
            self.assertTrue(all(compatible(*s['score'],'football',market,option) for s in detail['topScores']))
