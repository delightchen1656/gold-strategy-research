"""Search higher-return variants of strategy A without ranking on 2025+ returns.

Candidates are ranked on 2021-2024 only. The 2025+ period is a constraint veto:
it can reject a candidate, but never changes the ordering among survivors.
"""
from dataclasses import asdict
import json
from pathlib import Path

from research_execution_v2 import Spec, evaluate, feasible, load_inputs

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research/return-improvement-2026-09-08"


def score(result):
    """Worst-product compounded annual return over the two pre-2025 stages."""
    values = []
    for product in result.values():
        growth = 1.0
        for stage in list(product["splits"].values())[:2]:
            growth *= 1 + stage["return_pct"] / 100
        values.append(growth ** 0.25 - 1)
    return min(values)


def candidates():
    # Pre-registered before results are evaluated. Maximum target can be 100%,
    # but every stage's realised average weight must stay <=70%.
    for horizon in [60, 90, 120, 150]:
        for cap in [.85, .95, 1.00]:
            for vol_target in [.12, .14, .16]:
                for stop in [.08, .10, .12, .14]:
                    for frequency in ["monthly", "weekly"]:
                        for band in [.05, .10]:
                            for cooldown in [5, 10]:
                                yield Spec("vol_trend", horizon=horizon, cap=cap,
                                           vol_target=vol_target, stop=stop,
                                           frequency=frequency, band=band,
                                           cooldown=cooldown)


def compact(result):
    return {
        product: {"full": data["full"], "splits": data["splits"]}
        for product, data in result.items()
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    gold, frame = load_inputs()
    pre_gold = gold.loc[:"2024-12-31"]
    pre_frame = frame.loc[:"2024-12-31"]
    rows = []
    for number, spec in enumerate(candidates(), 1):
        pre, _ = evaluate(spec, pre_gold, pre_frame)
        if feasible(pre, 2):
            rows.append({"spec": asdict(spec), "pre2025_score": score(pre),
                         "pre2025": compact(pre)})
    rows.sort(key=lambda x: x["pre2025_score"], reverse=True)
    shortlist = rows[:200]
    survivors = []
    for row in shortlist:
        spec = Spec(**row["spec"])
        result, _ = evaluate(spec, gold, frame)
        row["all_stages_eligible"] = feasible(result, 3)
        row["full"] = compact(result)
        if row["all_stages_eligible"]:
            survivors.append(row)
    # Survivors retain their pre-2025 ordering: 2025+ only vetoes candidates.
    selected = survivors[0] if survivors else None
    result = {"method": "1,152 predefined strategy-A parameter rows; rank on 2021-2024 only; 2025+ is a constraint veto only",
              "constraints": "Each product and each stage: max drawdown <15%, average realised weight <=70%",
              "total_candidates": number, "pre2025_eligible": len(rows),
              "shortlist_checked": len(shortlist), "survivors": len(survivors),
              "selected": selected,
              "top_pre2025": shortlist[:20]}
    (OUT / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if selected:
        print(json.dumps({"selected_spec": selected["spec"], "pre2025_score": selected["pre2025_score"],
                          "full": selected["full"], "survivors": len(survivors)}, ensure_ascii=False, indent=2))
    else:
        print("No survivor in the predefined shortlist.")


if __name__ == "__main__":
    main()
