"""Exploratory research: use CNY gold proxy, not USD London gold, as the signal input."""
from __future__ import annotations
import sys
from dataclasses import asdict
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from research_execution_v2 import Spec, Rules, make_signal, simulate, metrics, feasible, load_inputs, SPLITS, START, END
from research_return_improvement import candidates
OUT=ROOT/'research'/'cny-signal-exploration-2026-09-08'

def ev(spec,gold,frame,kind):
    # Both signals are causally lagged by make_signal when mapped to China NAV dates.
    if kind == 'blend':
      signal=(make_signal(spec,gold,frame.index)+make_signal(spec,frame['cmb_mid'],frame.index))/2
    else:
      source=gold if kind=='london_usd' else frame['cmb_mid']
      signal=make_signal(spec,source,frame.index)
    ans={}
    for p in ('cmb','fund'):
      det,_,_=simulate(frame,signal,p,spec,Rules())
      ans[p]={'full':metrics(det),'splits':{label:metrics(det,a,b) for label,a,b in SPLITS}}
    return ans

def score(r):
    vals=[]
    for p in r.values():
      g=1
      for x in list(p['splits'].values())[:2]:g*=1+x['return_pct']/100
      vals.append(g**.25-1)
    return min(vals)

def budget(r,n=3):
    return all(m['max_drawdown_pct']>-13 and m['average_weight_pct']<=65 for p in r.values() for m in list(p['splits'].values())[:n])

def compact(r):return {p:{'full':x['full'],'splits':x['splits']} for p,x in r.items()}
def main():
 OUT.mkdir(parents=True,exist_ok=True);g,f=load_inputs();pg=g.loc[:'2024-12-31'];pf=f.loc[:'2024-12-31']
 allout={}
 for kind in ('blend',):
  ranked=[]
  for s in candidates():
   r=ev(s,pg,pf,kind)
   if budget(r,2):ranked.append({'spec':asdict(s),'score':score(r),'pre':compact(r)})
  ranked.sort(key=lambda x:x['score'],reverse=True)
  sel=None
  for rank,row in enumerate(ranked,1):
   r=ev(Spec(**row['spec']),g,f,kind)
   if budget(r,3):sel={**row,'rank':rank,'full':compact(r)};break
  allout[kind]={'pre_eligible':len(ranked),'selected':sel}
  print(kind,sel['rank'],sel['score'],sel['spec'])
  for p in ('cmb','fund'):print(p,sel['full'][p]['full']['cagr_pct'],sel['full'][p]['full']['max_drawdown_pct'])
 (OUT/'result.json').write_text(json.dumps(allout,ensure_ascii=False,indent=2),encoding='utf8')
if __name__=='__main__':main()


