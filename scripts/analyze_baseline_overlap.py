"""Quantify holding and rebalance overlap among frozen strategies 1/2/3."""
from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]

def main():
    p=pd.read_csv(ROOT/"data/raw/market/london_gold_fixing.csv",parse_dates=["date"]).set_index("date")["london_gold_usd_oz"].astype(float)
    dxy=pd.read_csv(ROOT/"data/raw/market/yahoo_dollar_index.csv",parse_dates=["date"]).set_index("date")["close"].astype(float)
    ry=pd.read_csv(ROOT/"data/raw/macro/fred_us_10y_real_yield.csv",parse_dates=["date"],na_values=["."]).set_index("date")["value"].astype(float)
    d=pd.concat([p.rename("gold"),dxy.rename("dxy"),ry.rename("ry")],axis=1).sort_index().ffill().reindex(p.index)
    ret=p.pct_change()
    def vol(n):return ret.rolling(n).std()*np.sqrt(252)
    w=pd.DataFrame(index=p.index)
    w["strategy1"]=(.20/vol(15)).clip(.25,1)
    w["strategy2"]=(.20/vol(10)).clip(.25,1)
    base=(.20/vol(20)).clip(.25,1); macro=(d.dxy.pct_change(60)>.03)&(d.ry.diff(60)>.20)
    w["strategy3"]=base*np.where(macro,.5,1)
    w=w.shift(1).loc["2020-01-01":].dropna()
    changes=w.diff(); threshold=.01
    action=np.sign(changes.where(changes.abs()>=threshold,0))
    portfolio_returns=w.mul(p.pct_change().reindex(w.index),axis=0)
    pairs={}
    for a,b in [("strategy1","strategy2"),("strategy1","strategy3"),("strategy2","strategy3")]:
        aa=action[a]!=0;bb=action[b]!=0;same_day=aa&bb&(action[a]==action[b])
        a_dates=list(np.flatnonzero(aa.to_numpy()));b_dates=list(np.flatnonzero(bb.to_numpy()))
        def matched(window):
            return sum(any(abs(i-j)<=window and action[a].iloc[i]==action[b].iloc[j] for j in b_dates) for i in a_dates)
        pairs[f"{a}_{b}"]={
            "weight_correlation":round(float(w[a].corr(w[b])),4),
            "portfolio_return_correlation":round(float(portfolio_returns[a].corr(portfolio_returns[b])),4),
            "mean_absolute_weight_difference_pct":round(float((w[a]-w[b]).abs().mean()*100),2),
            "days_within_5pct_weight":round(float(((w[a]-w[b]).abs()<=.05).mean()*100),2),
            "action_days_a":int(aa.sum()),"action_days_b":int(bb.sum()),
            "same_day_same_direction_actions":int(same_day.sum()),
            "a_action_match_rate_same_day_pct":round(float(same_day.sum()/aa.sum()*100),2),
            "a_action_match_rate_within_1d_pct":round(float(matched(1)/len(a_dates)*100),2),
            "a_action_match_rate_within_3d_pct":round(float(matched(3)/len(a_dates)*100),2)
        }
    summary={"period":[str(w.index[0].date()),str(w.index[-1].date())],
             "average_weights":{c:round(float(w[c].mean()),4) for c in w},
             "all_three_full_weight_days_pct":round(float((w.eq(1).all(axis=1)).mean()*100),2),
             "all_three_within_5pct_days_pct":round(float((w.max(axis=1)-w.min(axis=1)<=.05).mean()*100),2),
             "macro_reduction_days_strategy3":int(macro.reindex(w.index).sum()),"pairs":pairs}
    (ROOT/"reports/baseline_overlap.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    w.to_csv(ROOT/"data/derived/baseline_daily_weights.csv",index_label="date")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
