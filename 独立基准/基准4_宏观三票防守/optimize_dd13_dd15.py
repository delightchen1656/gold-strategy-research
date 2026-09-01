"""Maximize 2020-to-latest return under 13% and 15% max-drawdown limits."""
from pathlib import Path
import itertools, json
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]; HERE=Path(__file__).resolve().parent
COST=.001; MIN_HOLD=7
def load(p,c): return pd.read_csv(p,parse_dates=["date"],na_values=["."]).set_index("date")[c].astype(float)
def lock_lots(desired):
 lots=[]; out=[]
 for i,want in enumerate(desired.fillna(0).clip(0,1)):
  cur=sum(x[1] for x in lots)
  if want>cur+1e-12: lots.append([i,want-cur])
  elif want<cur-1e-12:
   need=cur-want
   for lot in lots:
    if need<=1e-12: break
    if i-lot[0]>=MIN_HOLD:
     sold=min(need,lot[1]); lot[1]-=sold; need-=sold
   lots=[x for x in lots if x[1]>1e-12]
  out.append(sum(x[1] for x in lots))
 return pd.Series(out,index=desired.index)
def bt(g,target,start):
 p=g.loc[start:]; w=lock_lots(target.reindex(p.index).shift(1).fillna(0)); r=p.pct_change().fillna(0)
 turn=w.diff().abs().fillna(w.abs()); sr=w*r-COST*turn; eq=(1+sr).cumprod(); dd=eq/eq.cummax()-1
 return {"return_pct":float((eq.iloc[-1]-1)*100),"max_drawdown_pct":float(dd.min()*100),
         "average_weight_pct":float(w.mean()*100),"days_in_gold_pct":float((w>0).mean()*100),
         "full_weight_days_pct":float((w>=.999).mean()*100),"last_weight_pct":float(w.iloc[-1]*100),
         "turnover":float(turn.sum()),"equity":eq,"weight":w}
def main():
 g=load(ROOT/"data/raw/market/london_gold_fixing.csv","london_gold_usd_oz").dropna()
 aux=pd.concat({"dxy":load(ROOT/"data/raw/market/yahoo_dollar_index.csv","close"),
                "real":load(ROOT/"data/raw/macro/fred_us_10y_real_yield.csv","value"),
                "vix":load(ROOT/"data/raw/macro/fred_vix_close.csv","value")},axis=1).sort_index().ffill().reindex(g.index).ffill()
 vol=g.pct_change().rolling(20).std()*np.sqrt(252)
 votes=((aux.dxy.pct_change(60)<0).astype(int)+(aux.real.diff(60)<0).astype(int)+(aux.vix.pct_change(20)<=.15).astype(int))
 rows=[]; targets={}
 for ma,risk,cap,two,one in itertools.product([75,100,125,150,175,200,225,250],np.arange(.10,.301,.025),[.75,1.0],[.25,.40,.55,.70,.85],[0,.10,.20,.30]):
  full=(risk/vol).clip(.25,cap); trend=g>g.rolling(ma).mean(); target=pd.Series(0.,index=g.index)
  target[trend&(votes>=3)]=full[trend&(votes>=3)]
  target[trend&(votes==2)]=two*full[trend&(votes==2)]
  target[trend&(votes==1)]=one*full[trend&(votes==1)]
  name=f"ma{ma}_r{risk:.3f}_c{cap:.2f}_v2{two:.2f}_v1{one:.2f}"; targets[name]=target
  fullm=bt(g,target,"2020-01-01"); blind=bt(g,target,"2025-01-01")
  rows.append({"variant":name,"ma":ma,"risk":risk,"cap":cap,"two_vote_fraction":two,"one_vote_fraction":one,
   **{f"full_{k}":v for k,v in fullm.items() if k not in ("equity","weight")},
   **{f"blind_{k}":v for k,v in blind.items() if k not in ("equity","weight")}})
 df=pd.DataFrame(rows)
 # Exclude buy-and-hold lookalikes: exposure on under 90% of sessions and average weight below 75%.
 active=df[(df.full_days_in_gold_pct<90)&(df.full_average_weight_pct<75)]
 winners={}
 for limit in [13,15]:
  eligible=active[active.full_max_drawdown_pct>=-limit].sort_values(["full_return_pct","blind_return_pct"],ascending=False)
  win=eligible.iloc[0]; winners[str(limit)]=win.to_dict()
  target=targets[win.variant]; m=bt(g,target,"2020-01-01")
  pd.DataFrame({"gold_usd_oz":g.loc[m["equity"].index],"executed_weight":m["weight"],"equity":m["equity"]}).to_csv(HERE/f"dd{limit}_max_return_equity.csv",index_label="date")
 df.sort_values("full_return_pct",ascending=False).to_csv(HERE/"dd13_dd15_all_candidates.csv",index=False)
 report={"period":[str(g.loc["2020-01-01":].index[0].date()),str(g.index[-1].date())],"candidate_count":len(df),
  "constraints":{"minimum_holding_trading_days":7,"cost_per_weight_change":.001,"days_in_gold_pct_lt":90,"average_weight_pct_lt":75},
  "winners":winners,"warning":"Full-period maximum-return optimization is in-sample and is an upper-bound research result, not an unbiased forecast."}
 (HERE/"dd13_dd15_max_return.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
 keys=["variant","full_return_pct","full_max_drawdown_pct","full_average_weight_pct","full_days_in_gold_pct","full_full_weight_days_pct","full_last_weight_pct","blind_return_pct","blind_max_drawdown_pct"]
 print(json.dumps({k:{x:(v[x] if x=="variant" else round(float(v[x]),2)) for x in keys} for k,v in winners.items()},ensure_ascii=False,indent=2))
if __name__=="__main__": main()
