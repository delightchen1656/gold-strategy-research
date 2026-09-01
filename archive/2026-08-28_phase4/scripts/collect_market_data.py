"""Download free market, macro and fund-NAV history with no API keys."""
from __future__ import annotations

import csv
import io
import json
import os
import subprocess
import tempfile
import zipfile
from datetime import timedelta
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UA = "Mozilla/5.0 gold-research/0.1"


def get(url: str, headers: dict | None = None, timeout: int = 30) -> bytes:
    request_headers = {"User-Agent": UA}
    request_headers.update(headers or {})
    if os.name == "nt":
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False) as temp:
                temp_path = temp.name
            command = ["curl.exe", "-L", "--fail", "--silent", "--show-error", "--max-time", str(timeout), "-A", UA, "-o", temp_path]
            for key, value in (headers or {}).items():
                command.extend(["-H", f"{key}: {value}"])
            command.append(url)
            completed = subprocess.run(command, capture_output=True, timeout=timeout + 5)
            if completed.returncode == 0:
                return Path(temp_path).read_bytes()
            raise RuntimeError(completed.stderr.decode("utf-8", errors="replace").strip())
        finally:
            if temp_path:
                Path(temp_path).unlink(missing_ok=True)
    req = urllib.request.Request(url, headers=request_headers)
    last_error = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return response.read()
        except Exception as exc:
            last_error = exc
            time.sleep(1 + attempt)
    raise RuntimeError(f"download failed after retries: {url}: {last_error}")


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def collect_yahoo(name: str, symbol: str, start_epoch: int, end_epoch: int) -> dict:
    escaped = urllib.parse.quote(symbol, safe="")
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{escaped}?period1={start_epoch}&period2={end_epoch}&interval=1d&events=history"
    result = json.loads(get(url))["chart"]["result"][0]
    quote = result["indicators"]["quote"][0]
    adjusted = result["indicators"].get("adjclose", [{}])[0].get("adjclose", [])
    rows = []
    for index, stamp in enumerate(result.get("timestamp", [])):
        rows.append({
            "date": datetime.fromtimestamp(stamp, timezone.utc).date().isoformat(),
            "open": quote["open"][index], "high": quote["high"][index],
            "low": quote["low"][index], "close": quote["close"][index],
            "adj_close": adjusted[index] if index < len(adjusted) else None,
            "volume": quote["volume"][index]
        })
    write_csv(ROOT / f"data/raw/market/yahoo_{name}.csv", list(rows[0]), rows)
    return {"source": "yahoo", "series": name, "symbol": symbol, "rows": len(rows), "first": rows[0]["date"], "last": rows[-1]["date"]}


def collect_fred(name: str, series_id: str) -> dict:
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?" + urllib.parse.urlencode({"id": series_id})
    source_rows = list(csv.DictReader(io.StringIO(get(url).decode("utf-8-sig"))))
    rows = [{"date": row.get("DATE") or row.get("observation_date"), "value": row.get(series_id, "")} for row in source_rows]
    write_csv(ROOT / f"data/raw/macro/fred_{name}.csv", ["date", "value"], rows)
    valid = [row for row in rows if row["value"] not in ("", ".")]
    return {"source": "fred", "series": name, "symbol": series_id, "rows": len(valid), "first": valid[0]["date"], "last": valid[-1]["date"]}


def collect_fred_bundle(series: dict[str, str]) -> list[dict]:
    ids = ",".join(series.values())
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?" + urllib.parse.urlencode({"id": ids}, safe=",")
    bundle_path = ROOT / "data/raw/macro/fred_bundle.zip"
    cache_fresh = bundle_path.exists() and datetime.fromtimestamp(bundle_path.stat().st_mtime, timezone.utc) > datetime.now(timezone.utc) - timedelta(hours=12)
    if cache_fresh:
        payload = bundle_path.read_bytes()
    else:
        try:
            payload = get(url, timeout=60)
            bundle_path.parent.mkdir(parents=True, exist_ok=True)
            bundle_path.write_bytes(payload)
        except Exception:
            if not bundle_path.exists():
                raise
            payload = bundle_path.read_bytes()
    reports = []
    tables = []
    if payload.startswith(b"PK"):
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            for member in archive.namelist():
                if member.endswith(".csv"):
                    tables.append(list(csv.DictReader(io.StringIO(archive.read(member).decode("utf-8-sig")))))
    else:
        tables.append(list(csv.DictReader(io.StringIO(payload.decode("utf-8-sig")))))
    for name, series_id in series.items():
        source_rows = next((table for table in tables if table and series_id in table[0]), None)
        if source_rows is None:
            raise RuntimeError(f"FRED series missing from bundle: {series_id}")
        rows = [{"date": row.get("DATE") or row.get("observation_date"), "value": row.get(series_id, "")} for row in source_rows]
        write_csv(ROOT / f"data/raw/macro/fred_{name}.csv", ["date", "value"], rows)
        valid = [row for row in rows if row["value"] not in ("", ".")]
        reports.append({"source": "fred", "series": name, "symbol": series_id, "rows": len(valid), "first": valid[0]["date"], "last": valid[-1]["date"]})
    return reports


def collect_fund(code: str) -> dict:
    items, page, total = [], 1, None
    while total is None or len(items) < total:
        params = urllib.parse.urlencode({"fundCode": code, "pageIndex": page, "pageSize": 20})
        url = f"https://api.fund.eastmoney.com/f10/lsjz?{params}"
        payload = json.loads(get(url, {"Referer": "https://fundf10.eastmoney.com/"}).decode("utf-8"))
        batch = payload["Data"]["LSJZList"]
        total = int(payload["TotalCount"])
        if not batch:
            break
        items.extend(batch)
        page += 1
    rows = [{
        "date": x["FSRQ"], "nav": x["DWJZ"], "acc_nav": x["LJJZ"],
        "daily_return_pct": x["JZZZL"], "subscription_status": x["SGZT"],
        "redemption_status": x["SHZT"]
    } for x in reversed(items)]
    write_csv(ROOT / f"data/raw/funds/{code}_nav.csv", list(rows[0]), rows)
    return {"source": "eastmoney", "series": f"fund_{code}_nav", "symbol": code, "rows": len(rows), "first": rows[0]["date"], "last": rows[-1]["date"]}


def cached_fund_report(code: str) -> dict | None:
    path = ROOT / f"data/raw/funds/{code}_nav.csv"
    if not path.exists():
        return None
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    return {"source": "eastmoney_cache", "series": f"fund_{code}_nav", "symbol": code,
            "rows": len(rows), "first": rows[0]["date"], "last": rows[-1]["date"], "stale": True}


def main() -> None:
    config = json.loads((ROOT / "config/market_sources.json").read_text(encoding="utf-8"))
    start = int(datetime.fromisoformat(config["history_start"]).replace(tzinfo=timezone.utc).timestamp())
    end = int(datetime.now(timezone.utc).timestamp()) + 86400
    quality, errors = [], []
    jobs = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        for name, symbol in config["yahoo"].items():
            jobs.append((pool.submit(collect_yahoo, name, symbol, start, end), "yahoo", name))
        lookup = {future: (source, name) for future, source, name in jobs}
        for future in as_completed(lookup):
            source, name = lookup[future]
            try:
                quality.append(future.result())
            except Exception as exc:
                errors.append({"source": source, "series": name, "error": str(exc)})
    try:
        quality.extend(collect_fred_bundle(config["fred"]))
    except Exception as exc:
        errors.append({"source": "fred", "series": "bundle", "error": str(exc)})
    for code in config["funds"]:
        try:
            quality.append(collect_fund(code))
        except Exception as exc:
            cached = cached_fund_report(code)
            if cached:
                quality.append(cached)
            errors.append({"source": "eastmoney", "series": code, "error": str(exc), "cache_used": bool(cached)})
    report = {"collected_at_utc": datetime.now(timezone.utc).isoformat(), "series": quality, "errors": errors}
    output = ROOT / "data/quality/market_collection.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"successful_series": len(quality), "errors": errors}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
