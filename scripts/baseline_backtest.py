"""Transparent walk-forward baseline for 009505; intended as a pipeline test."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
HORIZON = 20
COST_PER_WEIGHT_CHANGE = 0.001


def load_close(name: str) -> pd.Series:
    df = pd.read_csv(ROOT / f"data/raw/market/yahoo_{name}.csv", parse_dates=["date"])
    return df.set_index("date")["close"].astype(float).rename(name)


def load_fred(name: str) -> pd.Series:
    df = pd.read_csv(ROOT / f"data/raw/macro/fred_{name}.csv", parse_dates=["date"], na_values=["."])
    return df.set_index("date")["value"].astype(float).rename(name)


def metrics(equity: pd.Series, daily: pd.Series) -> dict:
    total = equity.iloc[-1] / equity.iloc[0] - 1
    years = max((equity.index[-1] - equity.index[0]).days / 365.25, 0.01)
    annual = (equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1
    drawdown = equity / equity.cummax() - 1
    vol = daily.std() * np.sqrt(252)
    return {"total_return": float(total), "annualized_return": float(annual),
            "max_drawdown": float(drawdown.min()), "annualized_volatility": float(vol),
            "calmar": float(annual / abs(drawdown.min())) if drawdown.min() < 0 else None}


def main() -> None:
    fund = pd.read_csv(ROOT / "data/raw/funds/009505_nav.csv", parse_dates=["date"])
    fund = fund.set_index("date")["nav"].astype(float).rename("fund_nav")
    frame = pd.concat([
        fund, load_close("gold_futures"), load_close("dollar_index"), load_close("usd_cny"),
        load_close("vix"), load_close("brent"), load_close("sp500"), load_close("long_treasury_etf"),
        load_fred("us_10y_real_yield"), load_fred("us_10y_breakeven_inflation")
    ], axis=1).sort_index().ffill()
    frame = frame.loc[fund.index.min():fund.index.max()]

    features = pd.DataFrame(index=frame.index)
    price_cols = ["fund_nav", "gold_futures", "dollar_index", "usd_cny", "vix", "brent", "sp500", "long_treasury_etf"]
    for col in price_cols:
        for days in (5, 20, 60):
            features[f"{col}_ret_{days}"] = frame[col].pct_change(days)
        features[f"{col}_vol_20"] = frame[col].pct_change().rolling(20).std() * np.sqrt(252)
    for col in ("us_10y_real_yield", "us_10y_breakeven_inflation"):
        features[f"{col}_chg_5"] = frame[col].diff(5)
        features[f"{col}_chg_20"] = frame[col].diff(20)
    # At a pre-15:00 decision, yesterday's completed observations are the newest safe inputs.
    features = features.shift(1).reindex(fund.index)
    forward_return = fund.shift(-HORIZON) / fund - 1
    daily_fund_return = fund.pct_change().fillna(0)

    oos_dates = fund.index[fund.index >= pd.Timestamp("2022-01-01")]
    predictions = pd.Series(index=oos_dates, dtype=float)
    model = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), Ridge(alpha=10.0))
    last_fit_month = None
    fitted = False
    for date in oos_dates:
        # Labels ending after the decision date are unknowable and excluded.
        eligible = features.index[(features.index <= date - pd.Timedelta(days=35)) & forward_return.notna()]
        month = (date.year, date.month)
        if month != last_fit_month and len(eligible) >= 250:
            model.fit(features.loc[eligible], forward_return.loc[eligible])
            fitted, last_fit_month = True, month
        if fitted:
            predictions.loc[date] = model.predict(features.loc[[date]])[0]

    raw_weight = pd.Series(0.0, index=oos_dates)
    raw_weight[predictions > 0.002] = 0.25
    raw_weight[predictions > 0.010] = 0.50
    raw_weight[predictions > 0.020] = 0.75
    raw_weight[predictions > 0.035] = 1.00
    weight = raw_weight.copy()
    equity_values, peak = [], 1.0
    previous_equity, previous_weight = 1.0, 0.0
    for date in oos_dates:
        drawdown = previous_equity / peak - 1
        target = weight.loc[date]
        if drawdown <= -0.15: target = 0.0
        elif drawdown <= -0.12: target = min(target, 0.25)
        elif drawdown <= -0.10: target *= 0.5
        turnover = abs(target - previous_weight)
        ret = daily_fund_return.loc[date] * previous_weight - turnover * COST_PER_WEIGHT_CHANGE
        current = previous_equity * (1 + ret)
        equity_values.append(current)
        peak = max(peak, current)
        previous_equity, previous_weight = current, target
        weight.loc[date] = target
    equity = pd.Series(equity_values, index=oos_dates, name="strategy_equity")
    strategy_daily = equity.pct_change().fillna(0)
    benchmark_daily = daily_fund_return.loc[oos_dates]
    benchmark = (1 + benchmark_daily).cumprod().rename("benchmark_equity")
    output = pd.concat([fund.loc[oos_dates], predictions.rename("predicted_20d_return"), weight.rename("gold_weight"), equity, benchmark], axis=1)
    (ROOT / "data/derived").mkdir(parents=True, exist_ok=True)
    output.to_csv(ROOT / "data/derived/baseline_backtest.csv", index_label="date")
    report = {
        "warning": "Pipeline baseline, not an approved trading model",
        "period": [oos_dates[0].date().isoformat(), oos_dates[-1].date().isoformat()],
        "assumptions": {"signal_lag_days": 1, "forecast_horizon_trading_days": HORIZON,
                        "transaction_cost_per_weight_change": COST_PER_WEIGHT_CHANGE},
        "strategy": metrics(equity, strategy_daily),
        "buy_and_hold": metrics(benchmark, benchmark_daily),
        "latest": {"date": oos_dates[-1].date().isoformat(), "predicted_20d_return": float(predictions.iloc[-1]),
                   "model_weight": float(weight.iloc[-1])}
    }
    (ROOT / "reports/baseline_backtest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
