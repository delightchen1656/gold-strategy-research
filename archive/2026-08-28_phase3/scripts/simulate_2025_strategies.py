"""Simulate CNY 100k, long-or-cash execution for the ten direction rules."""
from pathlib import Path
import json
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
INITIAL, COST, HORIZON, EXIT_MOVE = 100000.0, .001, 60, .10


def simulate(price, signals, column):
    cash, units, entry_price, entry_i, trades = INITIAL, 0.0, None, None, []
    pending = None
    signal_map = signals.set_index("signal_date")[column].to_dict()
    dates = price.index
    for i, date in enumerate(dates):
        px = price.iloc[i]
        if pending == "buy" and units == 0:
            cash *= 1 - COST; units = cash / px; cash = 0.0
            entry_price, entry_i = px, i
            trades.append({"entry": str(date.date()), "entry_price": px})
        elif pending == "sell" and units > 0:
            cash = units * px * (1 - COST); units = 0.0
            trades[-1].update({"exit": str(date.date()), "exit_price": px, "exit_reason": "down_signal"})
            entry_price = entry_i = None
        pending = None

        if units > 0:
            move = px / entry_price - 1
            age = i - entry_i
            if abs(move) >= EXIT_MOVE or age >= HORIZON:
                cash = units * px * (1 - COST); units = 0.0
                reason = "profit_10pct" if move >= EXIT_MOVE else "stop_10pct" if move <= -EXIT_MOVE else "time_60d"
                trades[-1].update({"exit": str(date.date()), "exit_price": px, "exit_reason": reason})
                entry_price = entry_i = None

        call = signal_map.get(date)
        if call == "up" and units == 0 and i + 1 < len(dates): pending = "buy"
        elif call == "down" and units > 0 and i + 1 < len(dates): pending = "sell"

    final = cash if units == 0 else units * price.iloc[-1]
    completed = int(sum("exit" in t for t in trades))
    wins = int(sum(t.get("exit_price", price.iloc[-1]) > t["entry_price"] for t in trades))
    return {"final_cny": round(final, 2), "return_pct": round((final/INITIAL-1)*100, 2),
            "entries": int(len(trades)), "completed_trades": completed,
            "profitable_trades": wins, "open_position": units > 0, "trades": trades}


def main():
    price = pd.read_csv(ROOT / "data/raw/market/london_gold_fixing.csv", parse_dates=["date"])
    price = price.set_index("date")["london_gold_usd_oz"].astype(float)
    price = price.loc[price.index >= "2025-01-01"]
    signals = pd.read_csv(ROOT / "data/derived/ten_direction_experiments.csv", parse_dates=["signal_date"])
    signals = signals[signals.signal_date >= "2025-01-01"]
    strategy_cols = [c for c in signals if c[:2].isdigit()]
    results = {col: simulate(price, signals, col) for col in strategy_cols}
    buy_hold = INITIAL * price.iloc[-1] / price.iloc[0]
    report = {"period": [str(price.index[0].date()), str(price.index[-1].date())],
              "assumptions": {"initial_cny": INITIAL, "long_only": True, "currency_conversion": False,
                              "one_way_cost": COST, "entry": "next London fixing", "exit": "+/-10%, 60 days, or down signal"},
              "london_gold_buy_hold_cny": round(buy_hold, 2), "strategies": results}
    (ROOT / "reports/strategy_capital_2025.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    rows = [{"strategy":k, **{x:v[x] for x in ("final_cny","return_pct","entries","completed_trades","profitable_trades","open_position")}} for k,v in results.items()]
    pd.DataFrame(rows).sort_values("final_cny", ascending=False).to_csv(ROOT / "data/derived/strategy_capital_2025.csv", index=False)
    print(pd.DataFrame(rows).sort_values("final_cny", ascending=False).to_string(index=False))
    print(f"buy_hold={buy_hold:.2f}")


if __name__ == "__main__": main()
