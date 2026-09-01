"""Search higher-exposure Baseline 4 variants with controlled drawdown growth."""
from pathlib import Path
import itertools
import json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
COST, MIN_HOLD = 0.001, 7


def load(path, col):
    return pd.read_csv(path, parse_dates=["date"], na_values=["."]).set_index("date")[col].astype(float)


def lock_lots(desired):
    lots, out = [], []
    for i, wanted in enumerate(desired.fillna(0).clip(0, 1)):
        current = sum(x[1] for x in lots)
        if wanted > current + 1e-12:
            lots.append([i, wanted-current])
        elif wanted < current - 1e-12:
            need = current-wanted
            for lot in lots:
                if need <= 1e-12: break
                if i-lot[0] >= MIN_HOLD:
                    sold = min(need, lot[1]); lot[1] -= sold; need -= sold
            lots = [x for x in lots if x[1] > 1e-12]
        out.append(sum(x[1] for x in lots))
    return pd.Series(out, index=desired.index)


def bt(gold, target, start, end):
    p = gold.loc[start:end]
    desired = target.reindex(p.index).shift(1).fillna(0)
    w = lock_lots(desired)
    r = p.pct_change().fillna(0)
    turn = w.diff().abs().fillna(w.abs())
    sr = w*r-COST*turn
    eq = (1+sr).cumprod(); dd = eq/eq.cummax()-1
    years = max((eq.index[-1]-eq.index[0]).days/365.25, 1/252)
    ann = eq.iloc[-1]**(1/years)-1
    return {
        "return_pct": float((eq.iloc[-1]-1)*100),
        "annualized_return_pct": float(ann*100),
        "max_drawdown_pct": float(dd.min()*100),
        "average_weight_pct": float(w.mean()*100),
        "days_in_gold_pct": float((w>0).mean()*100),
        "last_weight_pct": float(w.iloc[-1]*100),
        "equity": eq,
        "weight": w,
    }


def main():
    gold = load(ROOT/"data/raw/market/london_gold_fixing.csv", "london_gold_usd_oz").dropna()
    aux = pd.concat({
        "dxy": load(ROOT/"data/raw/market/yahoo_dollar_index.csv", "close"),
        "real": load(ROOT/"data/raw/macro/fred_us_10y_real_yield.csv", "value"),
        "vix": load(ROOT/"data/raw/macro/fred_vix_close.csv", "value"),
    }, axis=1).sort_index().ffill().reindex(gold.index).ffill()
    ret = gold.pct_change(); vol20 = ret.rolling(20).std()*np.sqrt(252)
    votes = ((aux.dxy.pct_change(60)<0).astype(int)
             +(aux.real.diff(60)<0).astype(int)
             +(aux.vix.pct_change(20)<=.15).astype(int))

    rows, targets = [], {}
    # Three votes receive full risk weight; two votes receive a controlled fraction.
    for ma, risk, cap, two_vote_fraction in itertools.product(
        [100, 150, 200], [.10, .12, .14, .16], [.75, 1.0], [0, .25, .40, .60]
    ):
        trend = gold > gold.rolling(ma).mean()
        full = (risk/vol20).clip(.25, cap)
        target = pd.Series(0.0, index=gold.index)
        target[trend & (votes>=3)] = full[trend & (votes>=3)]
        target[trend & (votes==2)] = two_vote_fraction*full[trend & (votes==2)]
        name = f"ma{ma}_risk{risk:.2f}_cap{cap:.2f}_two{two_vote_fraction:.2f}"
        targets[name] = target
        train = bt(gold,target,"2020-01-01","2024-12-31")
        blind = bt(gold,target,"2025-01-01",str(gold.index[-1].date()))
        fullm = bt(gold,target,"2020-01-01",str(gold.index[-1].date()))
        # Selection uses pre-2025 only. Drawdowns beyond 15% receive a steep penalty.
        dd = abs(train["max_drawdown_pct"])
        score = train["annualized_return_pct"]/(max(dd,1)**0.85) - max(0,dd-15)*0.25
        rows.append({"variant":name,"ma":ma,"risk_target":risk,"cap":cap,
                     "two_vote_fraction":two_vote_fraction,"selection_score":score,
                     **{f"train_{k}":v for k,v in train.items() if k not in ("equity","weight")},
                     **{f"blind_{k}":v for k,v in blind.items() if k not in ("equity","weight")},
                     **{f"full_{k}":v for k,v in fullm.items() if k not in ("equity","weight")}})
    df = pd.DataFrame(rows)
    base = df[df.variant=="ma150_risk0.12_cap1.00_two0.00"].iloc[0]
    eligible = df[(df.train_return_pct>base.train_return_pct)
                  &(df.train_average_weight_pct>base.train_average_weight_pct)
                  &(df.train_max_drawdown_pct>=-15)]
    winner = eligible.sort_values("selection_score",ascending=False).iloc[0]
    top = eligible.sort_values("selection_score",ascending=False).head(10)
    df.sort_values("selection_score",ascending=False).to_csv(HERE/"higher_exposure_all_candidates.csv",index=False)
    top.to_csv(HERE/"higher_exposure_top10.csv",index=False)
    win_target = targets[winner.variant]
    win_full = bt(gold,win_target,"2020-01-01",str(gold.index[-1].date()))
    out = pd.DataFrame({"gold_usd_oz":gold.loc[win_full["equity"].index],
                        "target_weight":win_target.reindex(win_full["equity"].index),
                        "executed_weight":win_full["weight"],"equity":win_full["equity"]})
    out.to_csv(HERE/"baseline4_higher_exposure_equity.csv",index_label="date")
    report={"data_end":str(gold.index[-1].date()),"candidate_count":len(df),
            "selection_period":["2020-01-02","2024-12-31"],
            "blind_period":["2025-01-02",str(gold.index[-1].date())],
            "original":base.to_dict(),"winner":winner.to_dict(),
            "top10":top.to_dict("records"),
            "selection_note":"Winner selected only on pre-2025 data among candidates with higher return, higher exposure and max drawdown no worse than -15% in selection period."}
    (HERE/"higher_exposure_research.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"original":{k:round(float(base[k]),2) for k in ["full_return_pct","full_max_drawdown_pct","full_average_weight_pct","blind_return_pct","blind_max_drawdown_pct"]},
                      "winner":{k:(winner[k] if k=="variant" else round(float(winner[k]),2)) for k in ["variant","full_return_pct","full_max_drawdown_pct","full_average_weight_pct","blind_return_pct","blind_max_drawdown_pct","full_last_weight_pct"]}},ensure_ascii=False,indent=2))


if __name__=="__main__": main()
