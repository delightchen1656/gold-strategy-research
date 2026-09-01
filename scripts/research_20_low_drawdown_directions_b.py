"""Second batch of 20 distinct low-drawdown long/cash gold directions."""
from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]; COST=.001
def load(path,col): return pd.read_csv(path,parse_dates=["date"],na_values=["."]).set_index("date")[col].astype(float)
def rsi(p,n=14):
    d=p.diff();u=d.clip(lower=0).rolling(n).mean();v=-d.clip(upper=0).rolling(n).mean();return 100-100/(1+u/v.replace(0,np.nan))
def state_rule(entries,exits,index,cooldown=0):
    state=0.;wait=0;out=[]
    for dt in index:
        if state and bool(exits.loc[dt]): state=0.;wait=cooldown
        elif not state:
            if wait>0: wait-=1
            elif bool(entries.loc[dt]): state=1.
        out.append(state)
    return pd.Series(out,index=index)
def eval_bt(p,t,start,end):
    idx=p.loc[start:end].index;q=p.reindex(idx);w=t.reindex(idx).shift(1).fillna(0).clip(0,1);r=q.pct_change().fillna(0)
    turn=w.diff().abs().fillna(w.abs());eq=(1+w*r-COST*turn).cumprod();dd=eq/eq.cummax()-1;yrs=max((idx[-1]-idx[0]).days/365.25,1/252)
    return {"return_pct":(eq.iloc[-1]-1)*100,"annualized_return_pct":(eq.iloc[-1]**(1/yrs)-1)*100,"max_drawdown_pct":dd.min()*100,"average_weight_pct":w.mean()*100,"turnover":turn.sum()}
def main():
    g=load(ROOT/"data/raw/market/london_gold_fixing.csv","london_gold_usd_oz")
    aux=pd.concat({
      "dxy":load(ROOT/"data/raw/market/yahoo_dollar_index.csv","close"),
      "usdcny":load(ROOT/"data/raw/market/yahoo_usd_cny.csv","close"),
      "spx":load(ROOT/"data/raw/market/yahoo_sp500.csv","close"),
      "brent":load(ROOT/"data/raw/market/yahoo_brent.csv","close"),
      "tlt":load(ROOT/"data/raw/market/yahoo_long_treasury_etf.csv","close"),
      "nominal":load(ROOT/"data/raw/macro/fred_us_10y_nominal_yield.csv","value"),
      "real":load(ROOT/"data/raw/macro/fred_us_10y_real_yield.csv","value")},axis=1).sort_index().ffill().reindex(g.index).ffill()
    ret=g.pct_change();vol20=ret.rolling(20).std()*np.sqrt(252);risk=(.11/vol20).clip(.25,.75)
    ma20=g.rolling(20).mean();ma50=g.rolling(50).mean();ma100=g.rolling(100).mean();ma150=g.rolling(150).mean();ma200=g.rolling(200).mean()
    sd20=g.rolling(20).std(); upper=ma20+2*sd20; lower=ma20-2*sd20
    C={}
    # Different sampling horizons and persistence mechanisms.
    C["21_weekly_trend_confirm"] = risk.where((g>g.rolling(105).mean())&(g.pct_change(5)>0),0)
    C["22_monthly_trend_confirm"] = risk.where((g>g.rolling(210).mean())&(g.pct_change(21)>0),0)
    C["23_trailing_stop_10"] = state_rule(g>g.shift(1).rolling(60).max(),g<g.cummax()*.90,g.index,10)
    rolling_peak=g.rolling(126,min_periods=1).max();C["24_rolling_peak_stop"] = state_rule(g>ma100,g<rolling_peak*.88,g.index,20)
    atr=g.diff().abs().rolling(20).mean();chandelier=g.rolling(60).max()-4*atr
    C["25_chandelier_exit"] = state_rule(g>g.shift(1).rolling(60).max(),g<chandelier.shift(1),g.index,10)
    C["26_bollinger_breakout"] = state_rule(g>upper.shift(1),g<ma20,g.index,5)
    C["27_bollinger_reversion"] = state_rule((g<lower)&(g>ma200),(g>ma20)|(g<ma200),g.index,5)*.5
    rr=rsi(g);C["28_rsi_oversold_rebound"] = state_rule((rr.shift(1)<30)&(rr>=30)&(g>ma200),(rr>65)|(g<ma200),g.index,5)*.5
    ema12=g.ewm(span=12,adjust=False).mean();ema26=g.ewm(span=26,adjust=False).mean();macd=ema12-ema26;signal=macd.ewm(span=9,adjust=False).mean()
    C["29_macd_trend"] = risk.where((macd>signal)&(g>ma200),0)
    C["30_momentum_acceleration"] = risk.where((g.pct_change(20)>g.pct_change(60)/3)&(g.pct_change(60)>0)&(g>ma200),0)
    compression=vol20<vol20.rolling(126).quantile(.3)
    C["31_vol_compression_break"] = state_rule(compression.shift(1)&(g>g.shift(1).rolling(40).max()),g<ma50,g.index,10)
    vol_of_vol=vol20.rolling(20).std()
    C["32_stable_vol_trend"] = risk.where((g>ma200)&(vol_of_vol<vol_of_vol.rolling(126).median()),0)
    C["33_gold_spx_relative"] = risk.where((g/aux.spx)>(g/aux.spx).rolling(100).mean(),0)
    C["34_gold_oil_relative"] = risk.where(((g/aux.brent)>(g/aux.brent).rolling(100).mean())&(g>ma100),0)
    C["35_gold_bond_relative"] = risk.where(((g/aux.tlt)>(g/aux.tlt).rolling(100).mean())&(g>ma100),0)
    C["36_cny_confirmation"] = risk.where((g>ma150)&(aux.usdcny.pct_change(60)>=0),0)
    C["37_nominal_yield_falling"] = risk.where((g>ma100)&(aux.nominal.diff(40)<0),0)
    C["38_real_yield_level"] = risk.where((g>ma100)&(aux.real<aux.real.rolling(252).median()),0)
    C["39_two_day_crash_guard"] = risk.where((g>ma200)&(ret.rolling(2).sum()>-.04),0)
    base=(g>ma200)&(ma50>ma100);C["40_cooldown_reentry"] = state_rule(base,g<ma100,g.index,20)*risk
    assert len(C)==20
    splits={"train":("2020-01-01","2023-12-31"),"validation":("2024-01-01","2024-12-31"),"blind":("2025-01-01","2026-08-27"),"recent":("2026-02-01","2026-08-27"),"full":("2020-01-01","2026-08-27")}
    rows=[]
    for name,target in C.items():
      row={"strategy":name,"current_signal_weight_pct":round(float(target.iloc[-1])*100,2)}
      for split,(a,b) in splits.items():
        m=eval_bt(g,target,a,b)
        for k,v in m.items():row[f"{split}_{k}"]=round(v,2)
      row["preblind_score"]=round(row["train_annualized_return_pct"]+row["validation_annualized_return_pct"]+2*(row["train_max_drawdown_pct"]+row["validation_max_drawdown_pct"])-.25*abs(row["train_annualized_return_pct"]-row["validation_annualized_return_pct"]),2)
      rows.append(row)
    df=pd.DataFrame(rows);eligible=df[(df.train_return_pct>0)&(df.validation_return_pct>0)].sort_values("preblind_score",ascending=False)
    df.sort_values("preblind_score",ascending=False).to_csv(ROOT/"data/derived/twenty_low_drawdown_directions_b.csv",index=False)
    report={"candidate_count":20,"selection_rule":"2020-2024 only; positive train and validation returns","top5_preblind":eligible.head(5).to_dict("records"),"all":df.to_dict("records")}
    (ROOT/"reports/twenty_low_drawdown_directions_b.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"eligible":len(eligible),"top5":report["top5_preblind"]},ensure_ascii=False,indent=2))
if __name__=="__main__":main()
