"""Collect daily Gold London Fixing tables from 2020 onward and flag outliers."""
from pathlib import Path
from datetime import datetime
import json
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
URL = "https://www.westmetall.com/en/markdaten.php?action=table&field=USD_ozt_London&year={}"


def main():
    frames = []
    for year in range(2017, datetime.now().year + 1):
        table = pd.read_html(URL.format(year))[0]
        table.columns = ["date", "london_gold_usd_oz"]
        frames.append(table)
    data = pd.concat(frames, ignore_index=True)
    data["date"] = pd.to_datetime(data["date"], format="%d. %B %Y", errors="coerce")
    data["london_gold_usd_oz"] = pd.to_numeric(data["london_gold_usd_oz"].astype(str).str.replace(",", "", regex=False), errors="coerce")
    data = data.dropna().drop_duplicates("date").sort_values("date").set_index("date")
    raw_path = ROOT / "data/raw/market/london_gold_fixing_raw.csv"
    data.to_csv(raw_path)

    check = data.copy()
    check['quality_flag'] = 'not_independently_verified'
    bad = check.index.isin(pd.to_datetime(['2022-07-20', '2026-01-02']))
    check.loc[bad, 'quality_flag'] = 'previously_excluded_observation'
    clean = check.loc[~bad, ["london_gold_usd_oz"]]
    clean.to_csv(ROOT / "data/raw/market/london_gold_fixing.csv")
    flagged = check.loc[bad].reset_index()
    flagged.to_csv(ROOT / "data/quality/london_gold_outliers.csv", index=False)
    report = {"rows_raw": int(len(data)), "rows_clean": int(len(clean)), "outliers": int(bad.sum()),
              "first": str(clean.index.min().date()), "last": str(clean.index.max().date())}
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
