"""Dual-horizon gold temperature, cash/gold allocation and historical test."""
from pathlib import Path
import json
import math
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
COST = 0.001


def market(name):
    x = pd.read_csv(ROOT / f"data/raw/market/yahoo_{name}.csv", parse_dates=["date"])
    return x.set_index("date")["close"].astype(float).rename(name)


def fred(name):
    x = pd.read_csv(ROOT / f"data/raw/macro/fred_{name}.csv", parse_dates=["date"], na_values=["."])
    return x.set_index("date")["value"].astype(float).rename(name)


def zscore(series, window=504, minimum=126):
    mean = series.rolling(window, min_periods=minimum).mean()
    std = series.rolling(window, min_periods=minimum).std().replace(0, np.nan)
    return ((series - mean) / std).clip(-2.5, 2.5).fillna(0)


def event_series(index, half_life):
    result = pd.Series(0.0, index=index)
    files = list((ROOT / "data/curated").glob("seed_events_*.csv"))
    direction = {"bullish": 1.0, "bearish": -1.0, "mixed": 0.0}
    confidence = {"low": 0.3, "medium": 0.6, "high": 1.0}
    seen = set()
    for path in files:
        for row in pd.read_csv(path).to_dict("records"):
            key = (row["published_date"], row["url"])
            if key in seen: continue
            seen.add(key)
            date = pd.Timestamp(row["published_date"])
            impulse = direction.get(row["consensus_direction"], 0) * confidence.get(row["confidence"], 0)
            age = (index - date).days
            mask = age >= 0
            result.loc[mask] += impulse * np.exp(-math.log(2) * age[mask] / half_life)
    return result.clip(-2.5, 2.5)


def perf(equity, returns):
    dd = equity / equity.cummax() - 1
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    ann = (equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1
    return {"total_return": float(equity.iloc[-1] / equity.iloc[0] - 1), "annualized_return": float(ann),
            "max_drawdown": float(dd.min()), "annualized_volatility": float(returns.std() * np.sqrt(252)),
            "cash_day_ratio": None}


def main():
    london_raw = pd.read_csv(ROOT / "data/raw/market/london_gold_fixing.csv", parse_dates=["date"])
    gold = london_raw.set_index("date")["london_gold_usd_oz"].astype(float).rename("london_gold")
    all_data = pd.concat([gold, market("gold_futures"), market("dollar_index"), market("usd_cny"),
                          market("vix"), market("brent"), fred("us_10y_real_yield"),
                          fred("us_10y_breakeven_inflation")], axis=1).sort_index().ffill().reindex(gold.index)

    long_parts = pd.DataFrame(index=gold.index)
    long_parts["gold_trend_120"] = zscore(gold.pct_change(120))
    long_parts["gold_trend_250"] = zscore(gold.pct_change(250))
    long_parts["real_yield_level"] = -zscore(all_data.us_10y_real_yield)
    long_parts["real_yield_change_60"] = -zscore(all_data.us_10y_real_yield.diff(60))
    long_parts["dollar_trend_120"] = -zscore(all_data.dollar_index.pct_change(120))
    long_parts["usd_cny_120"] = zscore(all_data.usd_cny.pct_change(120))
    long_parts["inflation_expectation_60"] = zscore(all_data.us_10y_breakeven_inflation.diff(60))
    long_parts["events"] = event_series(gold.index, 45)
    long_weights = pd.Series({"gold_trend_120": .20, "gold_trend_250": .15, "real_yield_level": .15,
                              "real_yield_change_60": .10, "dollar_trend_120": .15, "usd_cny_120": .10,
                              "inflation_expectation_60": .05, "events": .10})

    short_parts = pd.DataFrame(index=gold.index)
    short_parts["gold_momentum_5"] = zscore(gold.pct_change(5))
    short_parts["gold_momentum_20"] = zscore(gold.pct_change(20))
    short_parts["dollar_change_5"] = -zscore(all_data.dollar_index.pct_change(5))
    short_parts["real_yield_change_5"] = -zscore(all_data.us_10y_real_yield.diff(5))
    short_parts["vix_change_5"] = zscore(all_data.vix.pct_change(5))
    short_parts["brent_change_5"] = zscore(all_data.brent.pct_change(5))
    short_parts["events"] = event_series(gold.index, 7)
    short_weights = pd.Series({"gold_momentum_5": .15, "gold_momentum_20": .20, "dollar_change_5": .15,
                               "real_yield_change_5": .20, "vix_change_5": .05, "brent_change_5": .05,
                               "events": .20})

    # Shift one fixing day: decisions cannot see the current day's completed London fixing.
    long_temp = (50 + 20 * long_parts.mul(long_weights).sum(axis=1)).clip(0, 100).shift(1).fillna(50)
    short_temp = (50 + 20 * short_parts.mul(short_weights).sum(axis=1)).clip(0, 100).shift(1).fillna(50)
    # Hysteresis: strict entry, but do not churn merely because temperature slips by one point.
    target_values, state = [], 0.0
    for date in gold.index:
        lt, st = long_temp.loc[date], short_temp.loc[date]
        if state == 0:
            if lt >= 60 and st >= 60: state = 1.0
            elif lt >= 55 and st >= 55: state = .5
            elif lt >= 60 and st >= 50: state = .25
        else:
            if lt < 48 or st < 45: state = 0.0
            elif lt >= 60 and st >= 60: state = 1.0
            elif lt >= 55 and st >= 52: state = max(state, .5)
        target_values.append(state)
    target = pd.Series(target_values, index=gold.index)

    test = gold.index[gold.index >= pd.Timestamp("2017-01-01")]
    gold_ret = gold.pct_change().fillna(0)
    equity, weights, previous_equity, previous_weight, peak = [], [], 1.0, 0.0, 1.0
    for date in test:
        desired = target.loc[date]
        dd = previous_equity / peak - 1
        if dd <= -.15: desired = 0
        elif dd <= -.12: desired = min(desired, .25)
        elif dd <= -.10: desired *= .5
        daily = previous_weight * gold_ret.loc[date] - abs(desired - previous_weight) * COST
        current = previous_equity * (1 + daily)
        equity.append(current); weights.append(desired)
        peak = max(peak, current); previous_equity, previous_weight = current, desired
    equity = pd.Series(equity, index=test)
    weights = pd.Series(weights, index=test)
    strategy_ret = equity.pct_change().fillna(0)
    benchmark = (1 + gold_ret.loc[test]).cumprod()
    result = pd.DataFrame({"london_gold_usd_oz": gold.loc[test], "long_temperature": long_temp.loc[test],
                           "short_temperature": short_temp.loc[test], "gold_weight": weights,
                           "strategy_equity": equity, "benchmark_equity": benchmark})
    result.to_csv(ROOT / "data/derived/dual_temperature_backtest.csv", index_label="date")
    strategy_metrics = perf(equity, strategy_ret); strategy_metrics["cash_day_ratio"] = float((weights == 0).mean())
    report = {"warning": "London-gold rule prototype; event history is incomplete and this is not yet an approved live signal",
              "period": [str(test[0].date()), str(test[-1].date())], "strategy": strategy_metrics,
              "buy_and_hold": perf(benchmark, gold_ret.loc[test]),
              "latest": {"date": str(test[-1].date()), "long_temperature": round(float(long_temp.loc[test[-1]]), 1),
                         "short_temperature": round(float(short_temp.loc[test[-1]]), 1),
                         "gold_weight": float(weights.iloc[-1]), "action": "cash" if weights.iloc[-1] == 0 else "hold_or_buy"}}
    (ROOT / "reports/dual_temperature_backtest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
