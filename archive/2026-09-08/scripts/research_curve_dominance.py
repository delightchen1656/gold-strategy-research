"""Search for a strict return/drawdown improvement over institutional V3.

Ranking uses 2021-2024 only.  The 2025+ period can reject a candidate but does
not change the pre-2025 order.  This is exploratory research, not a clean new
holdout, because the project has already inspected the later period.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from research_execution_v2 import Rules, Spec, hysteresis, load_inputs, metrics, simulate, SPLITS

OUT = ROOT / "research" / "curve-dominance-2026-09-08"


@dataclass(frozen=True)
class CurveSpec:
    horizon: int
    cap: float
    vol_target: float
    fast_days: int
    weak_scale: float
    stop: float
    frequency: str
    cooldown: int
    band: float


def candidates():
    for horizon in (90, 120, 150):
        for cap in (.95, 1.0):
            for vol_target in (.12, .14):
                for fast_days in (10, 20, 40):
                    for weak_scale in (0.0, .25, .50):
                        for stop in (.08, .10, .12):
                            for frequency in ("weekly", "monthly"):
                                for cooldown in (3, 5, 10):
                                    for band in (.05, .10):
                                        yield CurveSpec(horizon, cap, vol_target, fast_days,
                                                        weak_scale, stop, frequency, cooldown, band)


def signal_for(spec: CurveSpec, gold: pd.Series, product_index):
    returns = gold.pct_change(fill_method=None)
    vol = returns.rolling(40).std() * np.sqrt(252)
    slow = hysteresis(gold, spec.horizon, .02)
    fast_ma = gold.rolling(spec.fast_days).mean()
    fast_scale = pd.Series(np.where(gold >= fast_ma, 1.0, spec.weak_scale), index=gold.index)
    raw = slow * fast_scale * spec.cap * (spec.vol_target / vol).clip(.2, 1.0)
    raw = (raw.fillna(0) / .05).round() * .05
    drawdown = gold / gold.rolling(spec.horizon).max() - 1
    keys = gold.index.to_period("M" if spec.frequency == "monthly" else "W-FRI")
    review = np.r_[True, keys[1:] != keys[:-1]]
    target = 0.0
    blocked_until = -1
    values = []
    for i, (desired, dd, weak) in enumerate(zip(raw.to_numpy(), drawdown.to_numpy(),
                                                 (gold < fast_ma).fillna(False).to_numpy())):
        # Stops and fast deterioration act daily. Re-risking remains scheduled.
        if dd < -spec.stop:
            target = 0.0
            blocked_until = i + spec.cooldown
        elif weak and target > desired:
            target = float(desired)
        elif review[i] and i >= blocked_until:
            target = float(desired)
        values.append(target)
    s = pd.Series(values, index=gold.index)
    positions = s.index.searchsorted(product_index, side="left") - 1
    return np.array([s.iloc[j] if j >= 0 else 0.0 for j in positions])


def evaluate(spec: CurveSpec, gold, frame, rules=Rules()):
    signal = signal_for(spec, gold, frame.index)
    execution_spec = Spec("vol_trend", band=spec.band)
    result = {}
    for product in ("cmb", "fund"):
        detail, _, _ = simulate(frame, signal, product, execution_spec, rules)
        result[product] = {
            "full": metrics(detail),
            "splits": {label: metrics(detail, start, end) for label, start, end in SPLITS},
        }
    return result


def constraints(result, stages):
    return all(m["max_drawdown_pct"] > -15 and m["average_weight_pct"] <= 70
               for product in result.values()
               for m in list(product["splits"].values())[:stages])


def score(result):
    # Prefer the weaker product's return, with a smooth drawdown penalty.
    cagrs = [p["full"]["cagr_pct"] for p in result.values()]
    drawdowns = [-p["full"]["max_drawdown_pct"] for p in result.values()]
    return min(cagrs) - .20 * max(drawdowns)


def compact(result):
    return {p: {"full": v["full"], "splits": v["splits"]} for p, v in result.items()}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    gold, frame = load_inputs()
    pre_gold, pre_frame = gold.loc[:"2024-12-31"], frame.loc[:"2024-12-31"]
    ranked = []
    for spec in candidates():
        result = evaluate(spec, pre_gold, pre_frame)
        if constraints(result, 2):
            ranked.append({"spec": asdict(spec), "score": score(result), "pre": compact(result)})
    ranked.sort(key=lambda row: row["score"], reverse=True)

    # V3 thresholds. Strict improvement means higher CAGR and smaller drawdown
    # for both products, while retaining every phase constraint.
    baseline = {"cmb": {"cagr": 13.074347915677675, "drawdown": 10.879337091239172},
                "fund": {"cagr": 14.27720646302153, "drawdown": 12.83981321697949}}
    checked = []
    winner = None
    best = None
    for rank, row in enumerate(ranked[:300], 1):
        result = evaluate(CurveSpec(**row["spec"]), gold, frame)
        dominates = constraints(result, 3) and all(
            result[p]["full"]["cagr_pct"] > baseline[p]["cagr"] and
            -result[p]["full"]["max_drawdown_pct"] < baseline[p]["drawdown"]
            for p in ("cmb", "fund")
        )
        item = {**row, "rank": rank, "dominates_v3": dominates, "full": compact(result)}
        checked.append(item)
        if best is None or score(result) > score(best["full"]):
            best = item
        if dominates:
            winner = item
            break
    output = {"candidate_rows": sum(1 for _ in candidates()), "baseline_v3": baseline,
              "selection_rule": "Rank 2021-2024 only; 2025+ is constraint/dominance veto only.",
              "winner": winner, "best_checked": best,
              "checked_count": len(checked)}
    (OUT / "result.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"winner": winner, "best_checked": best}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
