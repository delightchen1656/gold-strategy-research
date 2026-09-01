"""Common strategies not covered earlier: ATR, oscillators, seasonality and relative strength."""
from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1];INITIAL=100000.;COST=.001;OLD=334919.23

def csv_series(path,col):
    x=pd.read_csv(path,parse_dates=["date"]);return x.set_index("date")[col].astype(float)
def bt(p,t):
    w=t.shift(1).fillna(0).clip(0,1);r=p.pct_change().fillna(0);sr=w*r-w.diff().abs().fillna(w.abs())*COST
    e=INITIAL*(1+sr).cumprod();dd=e/e.cummax()-1
    return {"final_cny":round(float(e.iloc[-1]),2),"return_pct":round(float((e.iloc[-1]/INITIAL-1)*100),2),
            "max_drawdown_pct":round(float(dd.min()*100),2),"turnover":round(float(w.diff().abs().sum()),2),"average_gold_weight":round(float(w.mean()),3)}
def state_rule(index,buy,sell,initial=0):
    state=initial;out=[]
    for d in index:
        if not state and bool(buy.loc[d]):state=1
        elif state and bool(sell.loc[d]):state=0
        out.append(state)
    return pd.Series(out,index=index,dtype=float)

def main():
    p=csv_series(ROOT/"data/raw/market/london_gold_fixing.csv","london_gold_usd_oz")
    dxy=csv_series(ROOT/"data/raw/market/yahoo_dollar_index.csv","close");oil=csv_series(ROOT/"data/raw/market/yahoo_brent.csv","close")
    gc=pd.read_csv(ROOT/"data/raw/market/yahoo_gold_futures.csv",parse_dates=["date"]).set_index("date")
    d=pd.concat([p.rename("gold"),dxy.rename("dxy"),oil.rename("oil"),gc.high.rename("high"),gc.low.rename("low")],axis=1).sort_index().ffill().reindex(p.index)
    ma20=p.rolling(20).mean();ma50=p.rolling(50).mean();ma200=p.rolling(200).mean();sd20=p.rolling(20).std()
    tr=pd.concat([(d.high-d.low).abs(),(d.high-d.gold.shift()).abs(),(d.low-d.gold.shift()).abs()],axis=1).max(axis=1);atr=tr.rolling(14).mean()
    high22=p.rolling(22).max();ema12=p.ewm(span=12,adjust=False).mean();ema26=p.ewm(span=26,adjust=False).mean();macd=ema12-ema26;macds=macd.ewm(span=9,adjust=False).mean()
    delta=p.diff();gain=delta.clip(lower=0).ewm(alpha=1/14,adjust=False).mean();loss=(-delta.clip(upper=0)).ewm(alpha=1/14,adjust=False).mean();rsi=100-100/(1+gain/loss)
    z=(p-ma20)/sd20;vol=p.pct_change().rolling(20).std()*np.sqrt(252);vt=(.20/vol).clip(.25,1)
    S={}
    S["01_chandelier_3atr"]=state_rule(p.index,p>ma50,p<high22-3*atr,1)
    S["02_chandelier_4atr"]=state_rule(p.index,p>ma50,p<high22-4*atr,1)
    S["03_macd_cross"]=(macd>macds).astype(float)
    S["04_core50_macd"]=.5+.5*(macd>macds)
    S["05_rsi50_trend"]=(rsi>50).astype(float)
    S["06_rsi_pullback_uptrend"]=state_rule(p.index,(rsi<45)&(p>ma200),(rsi>70)|(p<ma200))
    S["07_bollinger_mid_trend"]=(p>ma20).astype(float)
    S["08_bollinger_mean_revert"]=state_rule(p.index,z<-1,z>.5)
    good_month=p.index.month.isin([1,2,7,8,9,12]);S["09_fixed_seasonal_core50"]=pd.Series(np.where(good_month,1,.5),index=p.index)
    S["10_gold_dollar_relative"]=((p.pct_change(60)-d.dxy.pct_change(60))>0).astype(float)
    ratio=p/d.oil;S["11_gold_oil_ratio_trend"]=(ratio>ratio.rolling(100).mean()).astype(float)
    chandelier_ok=p>=high22-4*atr;S["12_voltarget_chandelier"]=vt*np.where(chandelier_ok,1,.5)
    S["13_voltarget_macd_floor"]=vt*(.75+.25*(macd>macds))
    S["14_voltarget_seasonal"]=vt*np.where(good_month,1,.8)

    mask=p.index>=pd.Timestamp("2020-01-01");res={k:bt(p.loc[mask],v.loc[mask]) for k,v in S.items()}
    rows=pd.DataFrame([{"strategy":k,**v} for k,v in res.items()]).sort_values("final_cny",ascending=False);winner=rows.iloc[0].to_dict();replace=bool(winner["final_cny"]>OLD)
    report={"old_champion_cny":OLD,"winner":winner,"replace":replace,"strategies":res};(ROOT/"reports/missing_common_strategies.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    rows.to_csv(ROOT/"data/derived/missing_common_strategies.csv",index=False)
    if replace:(ROOT/"config/return_champion.json").write_text(json.dumps({"name":winner["strategy"],"selected_at":"2026-08-28","phase":5,"metrics":winner},ensure_ascii=False,indent=2),encoding="utf-8")
    print(rows.to_string(index=False));print(json.dumps({"replace":replace,"winner":winner},ensure_ascii=False,indent=2))
if __name__=="__main__":main()
