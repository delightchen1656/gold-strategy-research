"""Create objective consolidation -> first 10% breakout labels for London gold."""
from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
LOOKBACK, HORIZON, MOVE = 20, 60, .10


def main():
    price = pd.read_csv(ROOT / "data/raw/market/london_gold_fixing.csv", parse_dates=["date"])
    price = price.set_index("date")["london_gold_usd_oz"].astype(float)
    rolling_high = price.rolling(LOOKBACK).max()
    rolling_low = price.rolling(LOOKBACK).min()
    range_pct = rolling_high / rolling_low - 1
    return_pct = price / price.shift(LOOKBACK - 1) - 1
    flat = (range_pct <= .08) & (return_pct.abs() <= .04)
    # A state machine prevents one noisy day from turning one range into many cases.
    confirmed = flat.rolling(3).sum().eq(3)
    candidates = pd.Series(False, index=price.index)
    armed, nonflat_run = True, 0
    for i, is_flat in enumerate(flat):
        nonflat_run = 0 if is_flat else nonflat_run + 1
        if not armed and nonflat_run >= 5:
            armed = True
        if armed and confirmed.iloc[i]:
            candidates.iloc[i] = True
            armed = False
    rows = []
    positions = np.flatnonzero(candidates.to_numpy())
    for i in positions:
        if i + 1 >= len(price):
            continue
        start = price.iloc[i]
        future = price.iloc[i + 1:i + 1 + HORIZON]
        label, hit_date, hit_return = "unresolved", None, None
        for date, value in future.items():
            move = value / start - 1
            if move >= MOVE:
                label, hit_date, hit_return = "up", date, move
                break
            if move <= -MOVE:
                label, hit_date, hit_return = "down", date, move
                break
        rows.append({
            "signal_date": price.index[i], "price": start, "range_20d": range_pct.iloc[i],
            "return_20d": return_pct.iloc[i], "label": label,
            "hit_date": hit_date, "first_passage_return": hit_return,
            "days_observed": len(future), "future_max_return": future.max() / start - 1,
            "future_min_return": future.min() / start - 1
        })
    labels = pd.DataFrame(rows)
    output = ROOT / "data/derived/consolidation_breakout_labels.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    labels.to_csv(output, index=False)
    resolved = labels[labels.label != "unresolved"]
    report = {
        "definition": {"lookback_days": LOOKBACK, "max_range": .08, "max_abs_return": .04,
                       "confirmation_days": 3, "reset_nonconsolidation_days": 5,
                       "future_horizon_days": HORIZON, "first_passage_threshold": MOVE},
        "candidate_consolidations": int(len(labels)), "resolved_breakouts": int(len(resolved)),
        "up": int((resolved.label == "up").sum()), "down": int((resolved.label == "down").sum()),
        "unresolved": int((labels.label == "unresolved").sum()),
        "by_split": {
            "train_2017_2023": int((labels.signal_date < "2024-01-01").sum()),
            "validation_2024": int(((labels.signal_date >= "2024-01-01") & (labels.signal_date < "2025-01-01")).sum()),
            "blind_2025_present": int((labels.signal_date >= "2025-01-01").sum())
        }
    }
    (ROOT / "reports/consolidation_breakout_labels.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
