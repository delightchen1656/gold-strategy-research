"""Third batch: ten return-first long/cash strategies and automatic champion comparison."""
from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
INITIAL,COST,OLD_CHAMPION=100000.0,.001,278590.09

def market(name):
    x=pd.read_csv(ROOT/f"data/raw/market/yahoo_{name}.csv",parse_dates=["date"])
    return x.set_index("date")["close"].astype(float)

def fred(name):
    x=pd.read_csv(ROOT/f"data/raw/macro/fred_{name}.csv",parse_dates=["date"],na_values=["."])
    return x.set_index("date")["value"].astype(float)

def bt(price,target):
    w=target.shift(1).fillna(0).clip(0,1); r=price.pct_change().fillna(0)
    sr=w*r-w.diff().abs().fillna(w.abs())*COST
    eq=INITIAL*(1+sr).cumprod(); dd=eq/eq.cummax()-1
    return {"final_cny":round(float(eq.iloc[-1]),2),"return_pct":round(float((eq.iloc[-1]/INITIAL-1)*100),2),
            "max_drawdown_pct":round(float(dd.min()*100),2),"turnover":round(float(w.diff().abs().sum()),2),
            "average_gold_weight":round(float(w.mean()),3)}

def hysteresis(index,on,off,initial=0):
    state=initial; out=[]
    for d in index:
        if not state and bool(on.loc[d]): state=1
        elif state and bool(off.loc[d]): state=0
        out.append(state)
    return pd.Series(out,index=index,dtype=float)

def main():
    gold=pd.read_csv(ROOT/"data/raw/market/london_gold_fixing.csv",parse_dates=["date"]).set_index("date")["london_gold_usd_oz"].astype(float)
    d=pd.concat([gold.rename("gold"),market("dollar_index").rename("dxy"),market("vix").rename("vix"),
                 fred("us_10y_real_yield").rename("real_yield")],axis=1).sort_index().ffill().reindex(gold.index)
    ma20=gold.rolling(20).mean();ma50=gold.rolling(50).mean();ma100=gold.rolling(100).mean();ma200=gold.rolling(200).mean()
    ret60=gold.pct_change(60);ret120=gold.pct_change(120);vol20=gold.pct_change().rolling(20).std()*np.sqrt(252)
    dd=gold/gold.cummax()-1; dxy60=d.dxy.pct_change(60); ry60=d.real_yield.diff(60)
    S={}
    S["01_ma100_hysteresis"]=hysteresis(gold.index,gold>ma100*1.01,gold<ma100*.97)
    S["02_ma50_200_hysteresis"]=hysteresis(gold.index,ma50>ma200*1.01,ma50<ma200*.99)
    S["03_core75_ma100"]=.75+.25*(gold>ma100).astype(float)
    S["04_momentum_or_60_120"]=((ret60>0)|(ret120>0)).astype(float)
    S["05_graded_momentum"]=pd.Series(np.select([ret120>.10,ret120>0,ret120>-.10],[1,.75,.35],default=0),index=gold.index)
    macro_bad=(dxy60>.05)&(ry60>.30)
    S["06_macro_defensive_hold"]=(~macro_bad).astype(float)
    S["07_core50_trend_macro"]=.5+.5*((gold>ma100)&(~macro_bad)).astype(float)
    S["08_high_vol_break_defense"]=(~((vol20>.35)&(gold<ma50))).astype(float)
    tier=pd.Series(1.0,index=gold.index); tier[(dd<-.10)&(gold<ma100)]=.5; tier[(dd<-.15)&(gold<ma100)]=0
    S["09_drawdown_tiered"]=tier
    votes=pd.concat([(gold>ma100),(ma50>ma200),(ret120>0),(~macro_bad)],axis=1).sum(axis=1)
    S["10_continuous_regime_vote"]=(votes/4).clip(.25,1)

    mask=gold.index>=pd.Timestamp("2020-01-01")
    results={k:bt(gold.loc[mask],v.loc[mask]) for k,v in S.items()}
    rows=pd.DataFrame([{"strategy":k,**v} for k,v in results.items()]).sort_values("final_cny",ascending=False)
    winner=rows.iloc[0].to_dict(); replace=bool(winner["final_cny"]>OLD_CHAMPION)
    report={"period":[str(gold.loc[mask].index[0].date()),str(gold.loc[mask].index[-1].date())],
            "old_champion":{"name":"trend_low_vol","final_cny":OLD_CHAMPION},
            "new_winner":winner,"replace_champion":replace,"strategies":results}
    (ROOT/"reports/return_phase3_experiments.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    rows.to_csv(ROOT/"data/derived/return_phase3_experiments.csv",index=False)
    if replace:
        (ROOT/"config/return_champion.json").write_text(json.dumps({"name":winner["strategy"],"selected_at":"2026-08-28","basis":"highest 2020-present final capital among archived and phase3 candidates","metrics":winner},ensure_ascii=False,indent=2),encoding="utf-8")
    print(rows.to_string(index=False));print(json.dumps({"replace":replace,"winner":winner},ensure_ascii=False,indent=2))

if __name__=="__main__":main()
