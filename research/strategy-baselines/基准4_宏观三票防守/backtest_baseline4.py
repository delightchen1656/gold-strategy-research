"""Independent backtest for Baseline 4 (macro three-vote defense)."""
from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
START = "2020-01-01"
COST = 0.001
MIN_HOLD = 7
INITIAL_CNY = 50000.0


def load(path, column):
    return (
        pd.read_csv(path, parse_dates=["date"], na_values=["."])
        .set_index("date")[column]
        .astype(float)
    )


def lock_lots(desired):
    lots, out = [], []
    for i, wanted in enumerate(desired.fillna(0).clip(0, 1)):
        current = sum(amount for _, amount in lots)
        if wanted > current + 1e-12:
            lots.append([i, wanted - current])
        elif wanted < current - 1e-12:
            need = current - wanted
            for lot in lots:
                if need <= 1e-12:
                    break
                if i - lot[0] >= MIN_HOLD and lot[1] > 0:
                    sold = min(need, lot[1])
                    lot[1] -= sold
                    need -= sold
            lots = [lot for lot in lots if lot[1] > 1e-12]
        out.append(sum(amount for _, amount in lots))
    return pd.Series(out, index=desired.index)


def metrics(equity, returns, weight, turnover):
    drawdown = equity / equity.cummax() - 1
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    annualized = equity.iloc[-1] ** (1 / years) - 1
    downside = np.sqrt((returns.clip(upper=0) ** 2).mean()) * np.sqrt(252)
    return {
        "initial_cny": INITIAL_CNY,
        "final_cny": round(float(INITIAL_CNY * equity.iloc[-1]), 2),
        "return_pct": round(float((equity.iloc[-1] - 1) * 100), 2),
        "annualized_return_pct": round(float(annualized * 100), 2),
        "max_drawdown_pct": round(float(drawdown.min() * 100), 2),
        "calmar": round(float(annualized / abs(drawdown.min())), 3),
        "sortino": round(float(annualized / downside), 3) if downside else None,
        "average_gold_weight_pct": round(float(weight.mean() * 100), 2),
        "days_in_gold_pct": round(float((weight > 0).mean() * 100), 2),
        "rebalance_days": int((turnover > 1e-12).sum()),
        "total_turnover": round(float(turnover.sum()), 2),
        "last_executed_weight_pct": round(float(weight.iloc[-1] * 100), 2),
    }


def main():
    gold = load(ROOT / "data/raw/market/london_gold_fixing.csv", "london_gold_usd_oz").dropna()
    dxy = load(ROOT / "data/raw/market/yahoo_dollar_index.csv", "close")
    real_yield = load(ROOT / "data/raw/macro/fred_us_10y_real_yield.csv", "value")
    vix = load(ROOT / "data/raw/macro/fred_vix_close.csv", "value")
    aux = pd.concat({"dxy": dxy, "real": real_yield, "vix": vix}, axis=1).sort_index().ffill().reindex(gold.index).ffill()

    gold_return = gold.pct_change()
    vol20 = gold_return.rolling(20).std() * np.sqrt(252)
    risk_weight = (0.12 / vol20).clip(0.25, 1.00)
    favorable = (
        (gold > gold.rolling(150).mean())
        & (aux.dxy.pct_change(60) < 0)
        & (aux.real.diff(60) < 0)
        & (aux.vix.pct_change(20) <= 0.15)
    )
    raw_target = risk_weight.where(favorable, 0)

    price = gold.loc[START:]
    desired = raw_target.reindex(price.index).shift(1).fillna(0)
    weight = lock_lots(desired)
    daily_return = price.pct_change().fillna(0)
    turnover = weight.diff().abs().fillna(weight.abs())
    strategy_return = weight * daily_return - COST * turnover
    strategy_equity = (1 + strategy_return).cumprod()

    benchmark_equity = price / price.iloc[0]
    benchmark_return = benchmark_equity.pct_change().fillna(0)
    benchmark_turnover = pd.Series(0.0, index=price.index)
    benchmark_weight = pd.Series(1.0, index=price.index)

    report = {
        "strategy": "基准4｜宏观三票防守",
        "source_strategy": "策略2",
        "period": [str(price.index[0].date()), str(price.index[-1].date())],
        "assumptions": {
            "signal_lag_fixings": 1,
            "minimum_holding_trading_days": MIN_HOLD,
            "cost_per_weight_change_pct": COST * 100,
            "shorting": False,
            "leverage": False,
        },
        "baseline_4": metrics(strategy_equity, strategy_return, weight, turnover),
        "london_gold_buy_hold": metrics(benchmark_equity, benchmark_return, benchmark_weight, benchmark_turnover),
        "raw_signal_at_end_pct": round(float(raw_target.loc[price.index[-1]] * 100), 2),
    }
    (HERE / "backtest_2020_to_latest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    pd.DataFrame({
        "gold_usd_oz": price,
        "raw_target_weight": raw_target.reindex(price.index),
        "executed_weight": weight,
        "baseline4_equity": strategy_equity,
        "london_gold_equity": benchmark_equity,
    }).to_csv(HERE / "backtest_2020_to_latest.csv", index_label="date")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
