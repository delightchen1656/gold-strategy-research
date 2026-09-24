"""Institutional-style selection for the gold strategy.

Parameters are ranked only on 2021-2024.  2025+ is a pure veto.
An internal 13% drawdown budget and 65% phase-average exposure budget
leave margin inside the user's 15% / 70% hard limits.
"""
from __future__ import annotations
from dataclasses import asdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from research_execution_v2 import Rules, Spec, evaluate, load_inputs
from research_return_improvement import candidates

OUT = ROOT / "research" / "institutional-v3-2026-09-08"


def compact(result):
    return {p: {"full": v["full"], "splits": v["splits"]} for p, v in result.items()}


def internal_budget(result, stages):
    """A deployment buffer, applied identically per product and stage."""
    return all(m["max_drawdown_pct"] > -13 and m["average_weight_pct"] <= 65
               for p in result.values() for m in list(p["splits"].values())[:stages])


def pre_score(result):
    """Maximise the weaker product's compounded 2021-24 CAGR."""
    product_cagrs = []
    for product in result.values():
        growth = 1.0
        for stage in list(product["splits"].values())[:2]:
            growth *= 1 + stage["return_pct"] / 100
        product_cagrs.append(growth ** .25 - 1)
    return min(product_cagrs)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    gold, frame = load_inputs()
    pre_gold, pre_frame = gold.loc[:"2024-12-31"], frame.loc[:"2024-12-31"]
    ranking = []
    for spec in candidates():
        result, _ = evaluate(spec, pre_gold, pre_frame)
        if internal_budget(result, 2):
            ranking.append({"spec": asdict(spec), "pre2025_score": pre_score(result),
                            "pre2025": compact(result)})
    ranking.sort(key=lambda row: row["pre2025_score"], reverse=True)

    selected = None
    checked = []
    for rank, row in enumerate(ranking, 1):
        result, _ = evaluate(Spec(**row["spec"]), gold, frame)
        eligible = internal_budget(result, 3)
        checked.append({"rank": rank, "spec": row["spec"], "pre2025_score": row["pre2025_score"],
                        "holdout_veto_pass": eligible})
        if eligible and selected is None:
            selected = {**row, "pre2025_rank": rank, "full": compact(result)}
            break
    if selected is None:
        raise RuntimeError("No candidate passed the frozen holdout veto.")

    spec = Spec(**selected["spec"])
    stress = {}
    for name, rules in {
        "one_extra_session_delay": Rules(delay=1),
        "cmb_double_spread": Rules(cmb_halfspread=5),
        "cmb_double_spread_and_0_1pct_slippage": Rules(cmb_halfspread=5, slippage=.001),
        "fund_standard_1_5pct_subscription_fee": Rules(buy_fee=.015),
        "fund_t7_settlement": Rules(settle_days=7),
    }.items():
        result, _ = evaluate(spec, gold, frame, rules)
        stress[name] = {"internal_budget_pass": internal_budget(result, 3), "results": compact(result)}

    output = {
        "selection": "1,152 predefined strategy-A parameter rows; rank on 2021-2024 only; 2025+ can only veto.",
        "internal_deployment_budget": "Each product, each phase: max drawdown <13%; average realised exposure <=65%.",
        "user_hard_limits": "Each product, each phase: max drawdown <15%; average realised exposure <=70%.",
        "pre2025_internal_eligible": len(ranking),
        "selected": selected,
        "holdout_checks_until_selected": checked,
        "stress": stress,
    }
    (OUT / "result.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"selected": selected["spec"], "pre2025_rank": selected["pre2025_rank"],
                      "full": selected["full"], "stress_pass": {k:v["internal_budget_pass"] for k,v in stress.items()}},
                     ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
