"""Versioned complete-market offer policy; preserve original priced snapshots."""
import argparse,copy
from pathlib import Path
import priced_choices as original
from display_odds import KEYS,valid_number
FILE='priced-complete-before-results.json'
POLICY='complete-market-price-v2'
def choose(entry,row,sport):
    filtered=copy.deepcopy(entry)
    for market,keys in KEYS[sport].items():
        if not all(valid_number((row.get('odds') or {}).get(k),1) for k in keys):
            filtered.get('markets',{}).pop(market,None)
    return original.choose(filtered,row,sport)
def freeze(root,now=None):
    return original.freeze(root,now,filename=FILE,policy=POLICY,chooser=choose)
def settle(root):
    return original.settle(root,filename=FILE,policy=POLICY,chooser=choose,evaluation_file='priced-complete-evaluation.json')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['freeze','settle']);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    (freeze if a.mode=='freeze' else settle)(a.output)
