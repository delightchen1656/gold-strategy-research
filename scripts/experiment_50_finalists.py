"""Fifty allocation strategies/combinations; produce final top three by 2020-present capital."""
from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1];INITIAL=100000.;COST=.001

def load(path,col):
    x=pd.read_csv(path,parse_dates=["date"],na_values=["."]);return x.set_index("date")[col].astype(float)
def bt(p,t):
    w=t.shift(1).fillna(0).clip(0,1);r=p.pct_change().fillna(0);sr=w*r-w.diff().abs().fillna(w.abs())*COST
    eq=INITIAL*(1+sr).cumprod();dd=eq/eq.cummax()-1
    return {"final_cny":round(float(eq.iloc[-1]),2),"return_pct":round(float((eq.iloc[-1]/INITIAL-1)*100),2),
            "max_drawdown_pct":round(float(dd.min()*100),2),"turnover":round(float(w.diff().abs().sum()),2),"average_weight":round(float(w.mean()),3)}
def main():
    p=load(ROOT/"data/raw/market/london_gold_fixing.csv","london_gold_usd_oz")
    dxy=load(ROOT/"data/raw/market/yahoo_dollar_index.csv","close");ry=load(ROOT/"data/raw/macro/fred_us_10y_real_yield.csv","value")
    d=pd.concat([p.rename("g"),dxy.rename("dxy"),ry.rename("ry")],axis=1).sort_index().ffill().reindex(p.index)
    ret=p.pct_change();ma={n:p.rolling(n).mean() for n in [20,50,100,200]};dd=p/p.cummax()-1
    ema12=p.ewm(span=12,adjust=False).mean();ema26=p.ewm(span=26,adjust=False).mean();macd=ema12-ema26;macds=macd.ewm(span=9,adjust=False).mean()
    def vt(target=.20,lookback=20,floor=.25):return (target/(ret.rolling(lookback).std()*np.sqrt(252))).clip(floor,1)
    base=vt();S={};i=0
    def add(label,s):
        nonlocal i;i+=1;S[f"{i:02d}_{label}"]=pd.Series(s,index=p.index).clip(0,1)
    for target in [.10,.12,.14,.16,.18,.20,.22,.25]:add(f"vol20_target{int(target*100)}",vt(target))
    for lb in [10,15,30,40,60,90,120]:add(f"vol{lb}_target20",vt(.20,lb))
    for floor in [.35,.45,.55,.65,.75]:add(f"vol20_floor{int(floor*100)}",vt(.20,20,floor))
    for n in [20,50,100,200]:add(f"vol20_ma{n}_overlay",base*(.75+.25*(p>ma[n])))
    for n in [20,60,120]:add(f"vol20_mom{n}_overlay",base*(.75+.25*(p.pct_change(n)>0)))
    add("vol20_macd_overlay",base*(.75+.25*(macd>macds)))
    month_sets=[([1,2,8,9,12],"classic"),([1,2,7,8,9,12],"broad"),([1,8,9,12],"narrow"),([1,2,3,8,9],"q1_autumn"),([1,7,8,9],"summer"),([1,2,11,12],"winter"),([2,7,8,9,12],"ex_jan")]
    for months,label in month_sets:add(f"vol20_season_{label}",base*(.8+.2*p.index.month.isin(months)))
    for threshold,factor in [(-.08,.75),(-.08,.5),(-.10,.75),(-.10,.5),(-.12,.75),(-.12,.5)]:add(f"vol20_dd{int(abs(threshold)*100)}_x{int(factor*100)}",base*np.where(dd<threshold,factor,1))
    dxy60=d.dxy.pct_change(60);ry60=d.ry.diff(60)
    for dx,rr,factor in [(.03,.20,.75),(.03,.20,.5),(.04,.25,.75),(.04,.25,.5),(.05,.30,.5)]:
        bad=(dxy60>dx)&(ry60>rr);add(f"vol20_macro_{int(dx*100)}_{int(rr*100)}_x{int(factor*100)}",base*np.where(bad,factor,1))
    add("ensemble_vol_core90",.5*base+.5*(.9+.1*(p>ma[100])))
    add("ensemble_vol_trend",.5*base+.5*((p>ma[100]).astype(float)))
    add("ensemble_vol_momentum",.5*base+.5*((p.pct_change(120)>0).astype(float)))
    votes=((p>ma[50]).astype(int)+(p>ma[100]).astype(int)+(p>ma[200]).astype(int)+(p.pct_change(120)>0).astype(int))/4
    add("ensemble_vol_fourvote",.6*base+.4*votes)
    assert len(S)==50,len(S)
    mask=p.index>=pd.Timestamp("2020-01-01");res={k:bt(p.loc[mask],v.loc[mask]) for k,v in S.items()}
    rows=pd.DataFrame([{"strategy":k,**v} for k,v in res.items()])
    archived=pd.DataFrame([{"strategy":"ARCHIVED_20_vol_target20","final_cny":334919.23,"return_pct":234.92,"max_drawdown_pct":-26.23,"turnover":11.58,"average_weight":.945},
                           {"strategy":"BENCHMARK_buy_hold","final_cny":302190.00,"return_pct":202.19,"max_drawdown_pct":-27.69,"turnover":1.0,"average_weight":1.0}])
    combined=pd.concat([rows,archived],ignore_index=True).sort_values("final_cny",ascending=False);top3=combined.head(3).to_dict("records")
    rows.sort_values("final_cny",ascending=False).to_csv(ROOT/"data/derived/fifty_strategy_results.csv",index=False)
    combined.to_csv(ROOT/"data/derived/final_strategy_leaderboard.csv",index=False)
    report={"count":50,"top3":top3,"strategies":res};(ROOT/"reports/fifty_strategy_finalists.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    winner=top3[0];(ROOT/"config/return_champion.json").write_text(json.dumps({"name":winner["strategy"],"selected_at":"2026-08-28","phase":6,"metrics":winner},ensure_ascii=False,indent=2),encoding="utf-8")
    (ROOT/"config/final_top3.json").write_text(json.dumps(top3,ensure_ascii=False,indent=2),encoding="utf-8")
    print(combined.head(15).to_string(index=False));print(json.dumps(top3,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
