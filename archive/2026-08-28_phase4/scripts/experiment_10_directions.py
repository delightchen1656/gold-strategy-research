"""Compare ten transparent direction hypotheses on consolidation cases."""
from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def load_market(name):
    x = pd.read_csv(ROOT / f"data/raw/market/yahoo_{name}.csv", parse_dates=["date"])
    return x.set_index("date")["close"].astype(float)


def load_fred(name):
    x = pd.read_csv(ROOT / f"data/raw/macro/fred_{name}.csv", parse_dates=["date"], na_values=["."])
    return x.set_index("date")["value"].astype(float)


def calls(up, down, index):
    out = pd.Series("abstain", index=index)
    out[up] = "up"; out[down] = "down"
    return out


def evaluate(actual, pred):
    acted = pred != "abstain"; correct = pred == actual; resolved = actual.isin(["up", "down"])
    up_mask, down_mask = actual.eq("up"), actual.eq("down")
    return {"predictions": int(acted.sum()), "correct": int(correct.sum()),
            "precision": round(float(correct.sum()/acted.sum()), 4) if acted.sum() else None,
            "coverage": round(float(acted.mean()), 4),
            "big_move_recall": round(float(correct.sum()/resolved.sum()), 4) if resolved.sum() else None,
            "up_recall": round(float((correct & up_mask).sum()/up_mask.sum()), 4) if up_mask.sum() else None,
            "down_recall": round(float((correct & down_mask).sum()/down_mask.sum()), 4) if down_mask.sum() else None}


def main():
    cases = pd.read_csv(ROOT / "data/derived/consolidation_breakout_labels.csv", parse_dates=["signal_date"])
    temps = pd.read_csv(ROOT / "data/derived/dual_temperature_backtest.csv", parse_dates=["date"]).set_index("date")
    gold = pd.read_csv(ROOT / "data/raw/market/london_gold_fixing.csv", parse_dates=["date"]).set_index("date")["london_gold_usd_oz"].astype(float)
    daily = pd.concat([gold.rename("gold"), load_market("dollar_index").rename("dxy"),
                       load_market("vix").rename("vix"), load_market("brent").rename("brent"),
                       load_fred("us_10y_real_yield").rename("real_yield")], axis=1).sort_index().ffill().reindex(gold.index)
    f = pd.DataFrame(index=gold.index)
    for n in (5, 20, 60, 120): f[f"gold_ret_{n}"] = daily.gold.pct_change(n)
    for n in (5, 20):
        f[f"dxy_ret_{n}"] = daily.dxy.pct_change(n)
        f[f"real_yield_chg_{n}"] = daily.real_yield.diff(n)
        f[f"vix_ret_{n}"] = daily.vix.pct_change(n)
    f = f.join(temps[["long_temperature", "short_temperature"]])
    x = cases.join(f, on="signal_date")
    idx = x.index

    r = {}
    r["01_dual_strict"] = calls((x.long_temperature>=52)&(x.short_temperature>=52), (x.long_temperature<=48)&(x.short_temperature<=48), idx)
    avg = (x.long_temperature+x.short_temperature)/2
    r["02_temperature_average"] = calls(avg>=54, avg<=46, idx)
    r["03_long_environment"] = calls(x.long_temperature>=55, x.long_temperature<=42, idx)
    r["04_momentum_alignment"] = calls((x.gold_ret_20>0)&(x.gold_ret_60>0), (x.gold_ret_20<0)&(x.gold_ret_60<0), idx)
    macro = -20*x.dxy_ret_20 - .12*x.real_yield_chg_20
    r["05_dollar_real_yield"] = calls(macro>.025, macro<-.025, idx)
    r["06_trend_continuation"] = calls((x.gold_ret_60>.03)&(x.gold_ret_120>.05), (x.gold_ret_60<-.03)&(x.gold_ret_120<-.05), idx)
    r["07_range_slope"] = calls(x.return_20d>.015, x.return_20d<-.015, idx)
    r["08_mean_reversion"] = calls(x.return_20d<-.025, x.return_20d>.025, idx)

    base_votes = pd.DataFrame({k:v for k,v in r.items() if k in ["01_dual_strict","04_momentum_alignment","05_dollar_real_yield","07_range_slope"]})
    up_votes=(base_votes=="up").sum(axis=1); down_votes=(base_votes=="down").sum(axis=1)
    r["09_majority_vote"] = calls((up_votes>=2)&(up_votes>down_votes), (down_votes>=2)&(down_votes>up_votes), idx)
    r["10_unanimous_selective"] = calls(up_votes>=3, down_votes>=3, idx)

    split_masks = {"train_2017_2023":x.signal_date<"2024-01-01",
                   "validation_2024":(x.signal_date>="2024-01-01")&(x.signal_date<"2025-01-01"),
                   "exploratory_2025_present":x.signal_date>="2025-01-01"}
    report = {name:{split:evaluate(x.loc[mask,"label"], pred.loc[mask]) for split,mask in split_masks.items()} for name,pred in r.items()}
    detail = x[["signal_date","label"]].copy()
    for name,pred in r.items(): detail[name]=pred
    detail.to_csv(ROOT / "data/derived/ten_direction_experiments.csv", index=False)
    (ROOT / "reports/ten_direction_experiments.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    summary=[]
    for name,result in report.items():
        row={"model":name}
        for split in split_masks:
            row[f"{split}_precision"]=result[split]["precision"]
            row[f"{split}_predictions"]=result[split]["predictions"]
        summary.append(row)
    print(pd.DataFrame(summary).to_string(index=False))


if __name__ == "__main__": main()
