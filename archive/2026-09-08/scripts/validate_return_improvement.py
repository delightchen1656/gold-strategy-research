"""Stress and neighbourhood checks for the frozen return-improvement winner."""
import json
from dataclasses import replace
from pathlib import Path

from research_execution_v2 import Rules, Spec, evaluate, feasible, load_inputs

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research/return-improvement-2026-09-08"


def compact(result):
    return {key: {"full": value["full"], "splits": value["splits"]}
            for key, value in result.items()}


def main():
    path = OUT / "result.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    selected = data["selected"]
    spec = Spec(**selected["spec"])
    gold, frame = load_inputs()
    stresses = {
        "one_extra_session_delay": Rules(delay=1),
        "cmb_double_spread": Rules(cmb_halfspread=5),
        "cmb_double_spread_plus_delay": Rules(cmb_halfspread=5, slippage=.001, delay=1),
        "fund_standard_1_5pct_purchase_fee": Rules(buy_fee=.015),
        "fund_t7_settlement": Rules(settle_days=7),
    }
    data["stress"] = {}
    for name, rules in stresses.items():
        result, _ = evaluate(spec, gold, frame, rules)
        data["stress"][name] = {"eligible_all_stages": feasible(result, 3), "results": compact(result)}
    variations = {
        "horizon_90": replace(spec, horizon=90),
        "horizon_150": replace(spec, horizon=150),
        "cap_95pct": replace(spec, cap=.95),
        "vol_target_12pct": replace(spec, vol_target=.12),
        "vol_target_16pct": replace(spec, vol_target=.16),
        "stop_12pct": replace(spec, stop=.12),
        "band_10pct": replace(spec, band=.10),
        "cooldown_10_days": replace(spec, cooldown=10),
    }
    data["parameter_neighbours"] = {}
    for name, variant in variations.items():
        result, _ = evaluate(variant, gold, frame)
        data["parameter_neighbours"][name] = {"spec": variant.__dict__,
                                                "eligible_all_stages": feasible(result, 3),
                                                "results": compact(result)}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"stress": {key: value["eligible_all_stages"] for key, value in data["stress"].items()},
                      "neighbours": {key: value["eligible_all_stages"] for key, value in data["parameter_neighbours"].items()}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
