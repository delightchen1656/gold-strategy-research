"""Twenty distinct long/cash allocation directions; replace champion only on higher final capital."""
from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
INITIAL,COST,OLD=100000.0,.001,280113.59

def series(path,value):
    x=pd.read_csv(path,parse_dates=["date"],na_values=["."])
    return x.set_index("date")[value].astype(float)

def bt(p,t):
    w=t.shift(1).fillna(0).clip(0,1);r=p.pct_change().fillna(0)
    sr=w*r-w.diff().abs().fillna(w.abs())*COST;eq=INITIAL*(1+sr).cumprod();dd=eq/eq.cummax()-1
    return {"final_cny":round(float(eq.iloc[-1]),2),"return_pct":round(float((eq.iloc[-1]/INITIAL-1)*100),2),
            "max_drawdown_pct":round(float(dd.min()*100),2),"turnover":round(float(w.diff().abs().sum()),2),
            "average_gold_weight":round(float(w.mean()),3)}

def main():
    gold=series(ROOT/"data/raw/market/london_gold_fixing.csv","london_gold_usd_oz")
    dxy=series(ROOT/"data/raw/market/yahoo_dollar_index.csv","close")
    vix=series(ROOT/"data/raw/market/yahoo_vix.csv","close")
    ry=series(ROOT/"data/raw/macro/fred_us_10y_real_yield.csv","value")
    d=pd.concat([gold.rename("g"),dxy.rename("dxy"),vix.rename("vix"),ry.rename("ry")],axis=1).sort_index().ffill().reindex(gold.index)
    ma20=gold.rolling(20).mean();ma50=gold.rolling(50).mean();ma100=gold.rolling(100).mean();ma200=gold.rolling(200).mean()
    vol=gold.pct_change().rolling(20).std()*np.sqrt(252);dd=gold/gold.cummax()-1
    dxy60=d.dxy.pct_change(60);ry60=d.ry.diff(60);macro_bad=(dxy60>.04)&(ry60>.25)
    S={}
    S["01_core90_ma100"]=.9+.1*(gold>ma100)
    S["02_core85_ma50"]=.85+.15*(gold>ma50)
    S["03_core90_ma200"]=.9+.1*(gold>ma200)
    S["04_core80_ma_stack"]=.8+.1*(ma50>ma100)+.1*(ma100>ma200)
    S["05_core75_lowvol_trend"]=.75+.25*((gold>ma100)&(vol<.30))
    S["06_macro_veto_half"]=pd.Series(np.where(macro_bad,.5,1),index=gold.index)
    S["07_technical_macro_veto"]=pd.Series(np.where((gold<ma100)&macro_bad,.25,1),index=gold.index)
    S["08_ma200_defensive_half"]=pd.Series(np.where(gold<ma200,.5,1),index=gold.index)
    S["09_graded_ma_stack"]=.4+.2*(gold>ma50)+.2*(gold>ma100)+.2*(gold>ma200)
    S["10_vol_target20"]=(.20/vol).clip(.25,1)
    S["11_vol_target25"]=(.25/vol).clip(.25,1)
    tier=pd.Series(1.0,index=gold.index);tier[dd<-.10]=.75;tier[dd<-.15]=.5
    S["12_drawdown_core_tiers"]=tier
    low60=gold.shift(1).rolling(60).min(); high20=gold.shift(1).rolling(20).max(); state=1;vals=[]
    for date in gold.index:
        if state and gold.loc[date]<low60.loc[date]:state=.5
        elif state<1 and gold.loc[date]>high20.loc[date]:state=1
        vals.append(state)
    S["13_breakdown_half_reentry"]=pd.Series(vals,index=gold.index)
    S["14_core50_month_momentum"]=.5+.5*(gold.pct_change(21)>0)
    mom12_1=gold.shift(21)/gold.shift(252)-1
    S["15_core50_twelve_one"]=.5+.5*(mom12_1>0)
    S["16_ma_slope_graded"]=.5+.25*(ma50.diff(20)>0)+.25*(ma100.diff(20)>0)
    S["17_real_yield_core"]=.75+.25*(ry60<=0)
    S["18_dollar_core"]=.75+.25*(dxy60<=0)
    S["19_four_factor_continuous"]=.4+.15*((gold>ma100).astype(int)+(ma50>ma200).astype(int)+(dxy60<=0).astype(int)+(ry60<=0).astype(int))
    bad=((gold<ma100).astype(int)+(dxy60>0).astype(int)+(ry60>0).astype(int)+(vol>.30).astype(int))
    S["20_adaptive_bad_count"]=(1-.15*bad).clip(.4,1)

    mask=gold.index>=pd.Timestamp("2020-01-01");results={k:bt(gold.loc[mask],v.loc[mask]) for k,v in S.items()}
    rows=pd.DataFrame([{"strategy":k,**v} for k,v in results.items()]).sort_values("final_cny",ascending=False)
    winner=rows.iloc[0].to_dict();replace=bool(winner["final_cny"]>OLD)
    report={"period":[str(gold.loc[mask].index[0].date()),str(gold.loc[mask].index[-1].date())],"old_champion_cny":OLD,
            "winner":winner,"replace":replace,"strategies":results}
    (ROOT/"reports/return_phase4_20.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    rows.to_csv(ROOT/"data/derived/return_phase4_20.csv",index=False)
    if replace:(ROOT/"config/return_champion.json").write_text(json.dumps({"name":winner["strategy"],"selected_at":"2026-08-28","phase":4,"metrics":winner},ensure_ascii=False,indent=2),encoding="utf-8")
    print(rows.to_string(index=False));print(json.dumps({"replace":replace,"winner":winner},ensure_ascii=False,indent=2))

if __name__=="__main__":main()
