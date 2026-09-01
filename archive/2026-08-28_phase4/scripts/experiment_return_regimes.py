"""Second-generation return-first strategies: daily long/cash regimes, no leverage."""
from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
INITIAL, COST = 100000.0, .001


def market(name):
    x=pd.read_csv(ROOT/f"data/raw/market/yahoo_{name}.csv",parse_dates=["date"])
    return x.set_index("date")["close"].astype(float)


def fred(name):
    x=pd.read_csv(ROOT/f"data/raw/macro/fred_{name}.csv",parse_dates=["date"],na_values=["."])
    return x.set_index("date")["value"].astype(float)


def backtest(price, target):
    # Today's completed fixing sets tomorrow's weight.
    weight=target.shift(1).fillna(0).clip(0,1)
    ret=price.pct_change().fillna(0)
    strategy=weight*ret-weight.diff().abs().fillna(weight.abs())*COST
    equity=INITIAL*(1+strategy).cumprod()
    dd=equity/equity.cummax()-1
    return {"final_cny":round(float(equity.iloc[-1]),2),"return_pct":round(float((equity.iloc[-1]/INITIAL-1)*100),2),
            "max_drawdown_pct":round(float(dd.min()*100),2),"turnover":round(float(weight.diff().abs().sum()),2),
            "average_gold_weight":round(float(weight.mean()),3)}


def main():
    gold=pd.read_csv(ROOT/"data/raw/market/london_gold_fixing.csv",parse_dates=["date"]).set_index("date")["london_gold_usd_oz"].astype(float)
    data=pd.concat([gold.rename("gold"),market("dollar_index").rename("dxy"),fred("us_10y_real_yield").rename("real_yield")],axis=1).sort_index().ffill().reindex(gold.index)
    ma20=gold.rolling(20).mean(); ma50=gold.rolling(50).mean(); ma100=gold.rolling(100).mean(); ma200=gold.rolling(200).mean()
    high60=gold.shift(1).rolling(60).max(); low20=gold.shift(1).rolling(20).min()
    signals={}
    signals["01_price_above_ma200"]=(gold>ma200).astype(float)
    signals["02_golden_cross_50_200"]=(ma50>ma200).astype(float)
    signals["03_momentum_120"]=(gold.pct_change(120)>0).astype(float)
    signals["04_momentum_60_120"]=((gold.pct_change(60)>0)&(gold.pct_change(120)>0)).astype(float)
    state=[]; held=0
    for date in gold.index:
        if not held and gold.loc[date]>high60.loc[date]: held=1
        elif held and gold.loc[date]<low20.loc[date]: held=0
        state.append(held)
    signals["05_donchian_60_20"]=pd.Series(state,index=gold.index,dtype=float)
    macro_ok=~((data.dxy.pct_change(60)>0.03)&(data.real_yield.diff(60)>0.25))
    signals["06_ma200_macro_filter"]=((gold>ma200)&macro_ok).astype(float)
    votes=pd.concat([(gold>ma200),(ma50>ma200),(gold.pct_change(120)>0),macro_ok],axis=1).sum(axis=1)
    signals["07_regime_majority"]=(votes>=3).astype(float)
    vol=gold.pct_change().rolling(20).std()*np.sqrt(252)
    signals["08_trend_low_vol"]=((gold>ma100)&(vol<.30)).astype(float)
    peak=gold.cummax(); drawdown=gold/peak-1
    signals["09_defensive_drawdown"]=~((drawdown<-.10)&(gold<ma100))
    signals["09_defensive_drawdown"]=signals["09_defensive_drawdown"].astype(float)
    signals["10_core_plus_trend"]=.5+.5*(gold>ma200).astype(float)

    test=gold.index>=pd.Timestamp("2020-01-01")
    results={name:backtest(gold.loc[test],signal.loc[test]) for name,signal in signals.items()}
    buyhold=INITIAL*gold.loc[test].iloc[-1]/gold.loc[test].iloc[0]
    report={"period":[str(gold.loc[test].index[0].date()),str(gold.loc[test].index[-1].date())],
            "buy_hold_cny":round(float(buyhold),2),"strategies":results}
    (ROOT/"reports/return_regime_experiments.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    rows=[{"strategy":k,**v} for k,v in results.items()]
    pd.DataFrame(rows).sort_values("final_cny",ascending=False).to_csv(ROOT/"data/derived/return_regime_experiments.csv",index=False)
    print(pd.DataFrame(rows).sort_values("final_cny",ascending=False).to_string(index=False)); print("buy_hold",round(buyhold,2))


if __name__=="__main__":main()
