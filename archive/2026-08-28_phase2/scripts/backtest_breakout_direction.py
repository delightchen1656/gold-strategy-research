"""Frozen-threshold breakout direction test with explicit abstentions."""
from pathlib import Path
import json
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
THRESHOLD = 52  # selected on 2024 validation only; blind period is never consulted


def score(part, prediction):
    acted = prediction != "abstain"
    correct = prediction == part.label
    resolved = part.label.isin(["up", "down"])
    return {
        "cases": int(len(part)), "predictions": int(acted.sum()), "correct": int(correct.sum()),
        "precision_counting_unresolved_as_loss": float(correct.sum() / acted.sum()) if acted.sum() else None,
        "coverage": float(acted.mean()),
        "big_move_recall": float(correct.sum() / resolved.sum()) if resolved.sum() else None,
        "up_predictions": int((prediction == "up").sum()), "down_predictions": int((prediction == "down").sum()),
        "abstentions": int((prediction == "abstain").sum())
    }


def main():
    labels = pd.read_csv(ROOT / "data/derived/consolidation_breakout_labels.csv", parse_dates=["signal_date"])
    temps = pd.read_csv(ROOT / "data/derived/dual_temperature_backtest.csv", parse_dates=["date"])
    data = labels.merge(temps[["date", "long_temperature", "short_temperature"]], left_on="signal_date", right_on="date", how="left")
    prediction = pd.Series("abstain", index=data.index)
    prediction[(data.long_temperature >= THRESHOLD) & (data.short_temperature >= THRESHOLD)] = "up"
    prediction[(data.long_temperature <= 100 - THRESHOLD) & (data.short_temperature <= 100 - THRESHOLD)] = "down"
    data["prediction"] = prediction
    data["correct"] = prediction == data.label
    data["split"] = "train_2020_2023"
    data.loc[(data.signal_date >= "2024-01-01") & (data.signal_date < "2025-01-01"), "split"] = "validation_2024"
    data.loc[data.signal_date >= "2025-01-01", "split"] = "blind_2025_present"
    data.to_csv(ROOT / "data/derived/breakout_direction_backtest.csv", index=False)
    report = {"warning": "Temperature-only baseline; historical news features are not yet backfilled",
              "threshold": THRESHOLD, "unresolved_policy": "a directional call without a 10% move in 60 days counts as a loss",
              "splits": {name: score(group, group.prediction) for name, group in data.groupby("split", sort=False)}}
    (ROOT / "reports/breakout_direction_backtest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
