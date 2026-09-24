"""Run and validate the sole current gold strategy: Baseline 1."""
from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from baseline_1_engine import Rules, Spec, load_inputs, make_signal, metrics, simulate, SPLITS

OUT = ROOT / "research" / "baseline-1"
BASE = Spec("vol_trend", horizon=120, cap=1.0, vol_target=.12, stop=.14,
            frequency="monthly", band=.05, cooldown=5)


def overlay_signal(gold, product_index, ma_days=90, extension=1.20, lock_cap=0.0):
    base = make_signal(BASE, gold, product_index)
    ratio = gold / gold.rolling(ma_days).mean()
    positions = ratio.index.searchsorted(product_index, side="left") - 1
    known_ratio = np.array([ratio.iloc[i] if i >= 0 else np.nan for i in positions])
    return np.where(known_ratio > extension, np.minimum(base, lock_cap), base)


def evaluate(gold, frame, rules=Rules(), ma_days=90, extension=1.20, lock_cap=0.0):
    signal = overlay_signal(gold, frame.index, ma_days, extension, lock_cap)
    result = {}
    for product in ("cmb", "fund"):
        detail, _, _ = simulate(frame, signal, product, BASE, rules)
        result[product] = {"full": metrics(detail),
                           "splits": {label: metrics(detail, start, end)
                                      for label, start, end in SPLITS}}
    return result


def compact(result):
    return {p: {"full": v["full"], "splits": v["splits"]} for p, v in result.items()}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    gold, frame = load_inputs()
    selected = evaluate(gold, frame)
    stress = {}
    for name, rules in {
        "one_day_delay": Rules(delay=1),
        "double_spread_plus_slippage": Rules(cmb_halfspread=5, slippage=.001),
        "fund_1_5pct_subscription": Rules(buy_fee=.015),
        "fund_t7_settlement": Rules(settle_days=7),
    }.items():
        stress[name] = compact(evaluate(gold, frame, rules))
    neighbours = {}
    for days, threshold, cap in [(60, 1.20, 0.0), (120, 1.20, 0.0),
                                 (90, 1.18, 0.0), (90, 1.22, 0.0),
                                 (90, 1.20, .10), (90, 1.20, .25)]:
        key = f"ma{days}_ext{threshold:.2f}_cap{cap:.2f}"
        neighbours[key] = compact(evaluate(gold, frame, ma_days=days,
                                            extension=threshold, lock_cap=cap))
    output = {"name": "基准1",
              "base_spec": asdict(BASE),
              "overlay": {"ma_days": 90, "extension": 1.20, "lock_cap": 0.0},
              "selected": compact(selected),
              "stress": stress, "neighbours": neighbours,
              "note": "Exploratory; later history has been observed in earlier project rounds."}
    (OUT / "result.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"selected": output["selected"],
                      "stress_full": {k: {p: v[p]["full"] for p in v} for k, v in stress.items()},
                      "neighbour_full": {k: {p: v[p]["full"] for p in v} for k, v in neighbours.items()}},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
