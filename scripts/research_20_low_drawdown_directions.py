"""Twenty distinct long/cash gold directions, selected without blind-test leakage."""
from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
COST = 0.001

def load(path, col):
    return pd.read_csv(path, parse_dates=["date"], na_values=["."]).set_index("date")[col].astype(float)

def stateful_breakout(price, high_n, low_n):
    high = price.shift(1).rolling(high_n).max()
    low = price.shift(1).rolling(low_n).min()
    state, values = 0.0, []
    for dt in price.index:
        if price.loc[dt] > high.loc[dt]: state = 1.0
        elif price.loc[dt] < low.loc[dt]: state = 0.0
        values.append(state)
    return pd.Series(values, index=price.index)

def rsi(price, n=14):
    diff = price.diff(); up = diff.clip(lower=0).rolling(n).mean(); down = -diff.clip(upper=0).rolling(n).mean()
    return 100 - 100 / (1 + up / down.replace(0, np.nan))

def evaluate(price, target, start, end):
    idx = price.loc[start:end].index
    p = price.reindex(idx); w = target.reindex(idx).shift(1).fillna(0).clip(0, 1)
    ret = p.pct_change().fillna(0); turnover = w.diff().abs().fillna(w.abs())
    eq = (1 + w * ret - COST * turnover).cumprod(); dd = eq / eq.cummax() - 1
    years = max((idx[-1] - idx[0]).days / 365.25, 1 / 252)
    return {"return_pct": (eq.iloc[-1]-1)*100, "annualized_return_pct": (eq.iloc[-1]**(1/years)-1)*100,
            "max_drawdown_pct": dd.min()*100, "average_weight_pct": w.mean()*100,
            "turnover": turnover.sum(), "equity": eq}

def main():
    g = load(ROOT/"data/raw/market/london_gold_fixing.csv", "london_gold_usd_oz")
    sources = {
        "dxy": load(ROOT/"data/raw/market/yahoo_dollar_index.csv", "close"),
        "real": load(ROOT/"data/raw/macro/fred_us_10y_real_yield.csv", "value"),
        "nominal": load(ROOT/"data/raw/macro/fred_us_10y_nominal_yield.csv", "value"),
        "breakeven": load(ROOT/"data/raw/macro/fred_us_10y_breakeven_inflation.csv", "value"),
        "vix": load(ROOT/"data/raw/macro/fred_vix_close.csv", "value"),
        "spx": load(ROOT/"data/raw/market/yahoo_sp500.csv", "close"),
        "brent": load(ROOT/"data/raw/market/yahoo_brent.csv", "close"),
    }
    x = pd.concat(sources, axis=1).sort_index().ffill().reindex(g.index).ffill()
    ret = g.pct_change(); vol20 = ret.rolling(20).std()*np.sqrt(252)
    ma50=g.rolling(50).mean(); ma100=g.rolling(100).mean(); ma150=g.rolling(150).mean(); ma200=g.rolling(200).mean()
    risk12=(.12/vol20).clip(.25,1); risk10=(.10/vol20).clip(.25,.75)
    c = {}
    c["01_ma200_cash"] = (g>ma200).astype(float)
    c["02_dual_ma50_200"] = ((g>ma200)&(ma50>ma200)).astype(float)
    c["03_ma150_rising"] = ((g>ma150)&(ma150.diff(40)>0)).astype(float)
    c["04_breakout_120_40"] = stateful_breakout(g,120,40)
    c["05_breakout_250_60"] = stateful_breakout(g,250,60)
    c["06_momentum_12_1"] = (g.shift(21)/g.shift(252)>1).astype(float)
    votes=(g.pct_change(20)>0).astype(int)+(g.pct_change(60)>0).astype(int)+(g.pct_change(120)>0).astype(int)
    c["07_momentum_three_vote"]=(votes/3).where(g>ma200,0)
    c["08_momentum_vol_target"] = risk12.where((g.pct_change(60)>0)&(g>ma200),0)
    peak=g.cummax(); draw=g/peak-1
    c["09_drawdown_tiers"] = pd.Series(np.select([draw>-.05,draw>-.10,draw>-.15],[1,.5,.25],default=0),index=g.index).where(g>ma200,0)
    c["10_low_vol_trend"] = risk10.where((g>ma200)&(vol20<.22),0)
    c["11_dollar_weakness"] = risk12.where((g>ma150)&(x.dxy.pct_change(60)<0),0)
    c["12_real_yield_falling"] = risk12.where((g>ma150)&(x.real.diff(60)<0),0)
    c["13_dollar_real_combo"] = risk12.where((g>ma150)&(x.dxy.pct_change(60)<0)&(x.real.diff(60)<0),0)
    c["14_vix_calm_trend"] = risk12.where((g>ma150)&(x.vix<25),0)
    spx_riskoff=(x.spx<x.spx.rolling(200).mean())&(x.vix>20)
    c["15_safe_haven_regime"] = risk12.where((g>ma150)&spx_riskoff,0)
    c["16_breakeven_rising"] = risk12.where((g>ma150)&(x.breakeven.diff(60)>0),0)
    c["17_rate_inflation_mix"] = risk12.where((g>ma150)&((x.real.diff(60)<0)|(x.breakeven.diff(60)>0)),0)
    c["18_oil_inflation_link"] = risk12.where((g>ma150)&(x.brent.pct_change(60)>0),0)
    rr=rsi(g,14); c["19_rsi_recovery"] = risk10.where((g>ma200)&(rr>40)&(rr<70),0)
    macro_votes=(x.dxy.pct_change(60)<0).astype(int)+(x.real.diff(60)<0).astype(int)+(x.breakeven.diff(60)>0).astype(int)+(x.vix<25).astype(int)
    technical_votes=(g>ma200).astype(int)+(ma50>ma200).astype(int)+(g.pct_change(60)>0).astype(int)
    c["20_seven_factor_vote"] = risk12.where((macro_votes+technical_votes)>=5,0)
    assert len(c)==20

    splits={"train":("2020-01-01","2023-12-31"),"validation":("2024-01-01","2024-12-31"),"blind":("2025-01-01","2026-08-27"),"recent":("2026-02-01","2026-08-27"),"full":("2020-01-01","2026-08-27")}
    rows=[]
    for name,target in c.items():
        row={"strategy":name,"current_signal_weight_pct":round(target.iloc[-1]*100,2)}
        for split,(start,end) in splits.items():
            m=evaluate(g,target,start,end)
            for k in ["return_pct","annualized_return_pct","max_drawdown_pct","average_weight_pct","turnover"]: row[f"{split}_{k}"]=round(m[k],2)
        # Pre-blind selection score: reward return, strongly penalize drawdown and instability.
        row["preblind_score"]=round(row["train_annualized_return_pct"]+row["validation_annualized_return_pct"]+2*(row["train_max_drawdown_pct"]+row["validation_max_drawdown_pct"])-abs(row["train_annualized_return_pct"]-row["validation_annualized_return_pct"])*.25,2)
        rows.append(row)
    table=pd.DataFrame(rows)
    eligible=table[(table.train_return_pct>0)&(table.validation_return_pct>0)].sort_values("preblind_score",ascending=False)
    table.sort_values("preblind_score",ascending=False).to_csv(ROOT/"data/derived/twenty_low_drawdown_directions.csv",index=False)
    benchmark={}
    for split,(start,end) in splits.items():
        q=g.loc[start:end];eq=q/q.iloc[0];dd=eq/eq.cummax()-1
        benchmark[split]={"return_pct":round((eq.iloc[-1]-1)*100,2),"max_drawdown_pct":round(dd.min()*100,2)}
    report={"candidate_count":20,"selection_rule":"ranked only on 2020-2024; positive train and validation return required","top5_preblind":eligible.head(5).to_dict("records"),"all":table.to_dict("records"),"benchmark":benchmark}
    (ROOT/"reports/twenty_low_drawdown_directions.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"top5_preblind":report["top5_preblind"],"benchmark":benchmark},ensure_ascii=False,indent=2))

if __name__=="__main__": main()
