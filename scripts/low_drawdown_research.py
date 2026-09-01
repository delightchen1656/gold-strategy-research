"""Low-drawdown, long/cash gold strategy research with strict time splits."""
from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
COST = 0.001

def load(path, col):
    return pd.read_csv(path, parse_dates=["date"], na_values=["."]).set_index("date")[col].astype(float)

def metrics(price, target, start, end):
    idx = price.loc[start:end].index
    p = price.reindex(idx)
    # Indicators/signals may use earlier history; execution begins from cash.
    w = target.reindex(idx).shift(1).fillna(0).clip(0, 1)
    r = p.pct_change().fillna(0)
    sr = w * r - w.diff().abs().fillna(w.abs()) * COST
    eq = (1 + sr).cumprod()
    dd = eq / eq.cummax() - 1
    years = max((idx[-1] - idx[0]).days / 365.25, 1 / 252)
    return {
        "start": str(idx[0].date()), "end": str(idx[-1].date()),
        "return_pct": round((eq.iloc[-1] - 1) * 100, 2),
        "annualized_return_pct": round((eq.iloc[-1] ** (1 / years) - 1) * 100, 2),
        "max_drawdown_pct": round(dd.min() * 100, 2),
        "average_weight_pct": round(w.mean() * 100, 2),
        "turnover": round(w.diff().abs().sum(), 2),
        "equity": eq, "weight": w,
    }

def main():
    gold = load(ROOT / "data/raw/market/london_gold_fixing.csv", "london_gold_usd_oz")
    dxy = load(ROOT / "data/raw/market/yahoo_dollar_index.csv", "close")
    real = load(ROOT / "data/raw/macro/fred_us_10y_real_yield.csv", "value")
    vix = load(ROOT / "data/raw/macro/fred_vix_close.csv", "value")
    aux = pd.concat([dxy.rename("dxy"), real.rename("real"), vix.rename("vix")], axis=1).sort_index().ffill().reindex(gold.index).ffill()
    ret = gold.pct_change()
    vol20 = ret.rolling(20).std() * np.sqrt(252)
    candidates = {}

    # Family A: defensive trend. Full cash when the long trend is broken.
    for ma in [100, 150, 200, 250]:
        for confirm in [0, 20, 40]:
            trend = gold > gold.rolling(ma).mean()
            if confirm:
                trend &= gold.rolling(ma).mean().diff(confirm) > 0
            risk = (.14 / vol20).clip(.25, 1)
            candidates[f"trend_ma{ma}_slope{confirm}"] = risk.where(trend, 0)

    # Family B: dual-horizon temperature. Long regime plus short momentum breadth.
    for long_ma in [150, 200, 250]:
        for short in [20, 40, 60]:
            long_ok = gold > gold.rolling(long_ma).mean()
            short_ok = gold.pct_change(short) > 0
            strong = long_ok & short_ok
            weak = long_ok ^ short_ok
            target = pd.Series(0.0, index=gold.index)
            target[weak] = .25
            target[strong] = (.12 / vol20).clip(.5, 1)[strong]
            candidates[f"dual_ma{long_ma}_mom{short}"] = target

    # Family C: macro shield. Requires trend and at least two favorable macro votes.
    dxy_change = aux.dxy.pct_change(60)
    real_change = aux.real.diff(60)
    vix_change = aux.vix.pct_change(20)
    for ma in [150, 200, 250]:
        for votes_needed in [1, 2, 3]:
            votes = (dxy_change < 0).astype(int) + (real_change < 0).astype(int) + (vix_change <= .15).astype(int)
            trend = gold > gold.rolling(ma).mean()
            target = pd.Series(0.0, index=gold.index)
            target[trend & (votes >= votes_needed)] = (.12 / vol20).clip(.25, 1)[trend & (votes >= votes_needed)]
            candidates[f"macro_ma{ma}_votes{votes_needed}"] = target

    splits = {"train": ("2020-01-01", "2023-12-31"), "validation": ("2024-01-01", "2024-12-31"), "blind": ("2025-01-01", "2026-08-27"), "full": ("2020-01-01", "2026-08-27")}
    rows = []
    for name, target in candidates.items():
        family = name.split("_")[0]
        row = {"strategy": name, "family": family}
        for split, (start, end) in splits.items():
            m = metrics(gold, target, start, end)
            for k in ["return_pct", "annualized_return_pct", "max_drawdown_pct", "average_weight_pct", "turnover"]:
                row[f"{split}_{k}"] = m[k]
        rows.append(row)
    table = pd.DataFrame(rows)

    # Selection uses train and validation only. Positive returns are required in both.
    selected = []
    for family in ["trend", "dual", "macro"]:
        f = table[(table.family == family) & (table.train_return_pct > 0) & (table.validation_return_pct > 0)].copy()
        f["selection_score"] = f.train_annualized_return_pct + f.validation_annualized_return_pct + 1.5 * (f.train_max_drawdown_pct + f.validation_max_drawdown_pct)
        selected.append(f.sort_values(["selection_score", "validation_max_drawdown_pct"], ascending=False).iloc[0])
    selected_df = pd.DataFrame(selected)

    benchmark = {}
    for split, (start, end) in splits.items():
        idx = gold.loc[start:end].index
        eq = gold.loc[idx] / gold.loc[idx].iloc[0]
        dd = eq / eq.cummax() - 1
        benchmark[split] = {"return_pct": round((eq.iloc[-1] - 1) * 100, 2), "max_drawdown_pct": round(dd.min() * 100, 2)}

    output_cols = [c for c in table.columns if not c.endswith("turnover")]
    table[output_cols].to_csv(ROOT / "data/derived/low_drawdown_candidates.csv", index=False)
    selected_details = []
    for _, row in selected_df.iterrows():
        name = row["strategy"]
        detail = {k: v for k, v in row[output_cols].to_dict().items()}
        detail["current_signal_weight_pct"] = round(float(candidates[name].iloc[-1]) * 100, 2)
        recent = metrics(gold, candidates[name], "2026-02-01", "2026-08-27")
        detail["recent_2026_feb_return_pct"] = recent["return_pct"]
        detail["recent_2026_feb_max_drawdown_pct"] = recent["max_drawdown_pct"]
        detail["recent_2026_feb_average_weight_pct"] = recent["average_weight_pct"]
        selected_details.append(detail)
    report = {
        "method": {"cost_per_weight_change": COST, "long_cash_only": True, "allow_zero_weight": True,
                   "selection_data": "2020-2024 only", "blind_test": "2025-01-01 to 2026-08-27"},
        "selected": selected_details, "benchmark": benchmark,
    }
    (ROOT / "reports/low_drawdown_research.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
