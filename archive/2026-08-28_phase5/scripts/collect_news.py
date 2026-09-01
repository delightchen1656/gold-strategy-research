"""Collect free official and market-consensus headlines into a raw JSONL archive.

The collector intentionally stores raw metadata only. Classification and trading
labels happen later so a headline cannot silently become a trade signal.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def text(node: ET.Element, names: tuple[str, ...]) -> str:
    for child in node.iter():
        tag = child.tag.rsplit("}", 1)[-1].lower()
        if tag in names and child.text:
            return child.text.strip()
    return ""


def normalized_time(value: str) -> str | None:
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def fetch_xml(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "gold-research/0.1"})
    with urllib.request.urlopen(req, timeout=10) as response:
        return response.read()


def parse_feed(payload: bytes, source: str, tier: int, feed_type: str) -> list[dict]:
    root = ET.fromstring(payload)
    rows = []
    for item in list(root.iter("item")) + [n for n in root.iter() if n.tag.rsplit("}", 1)[-1] == "entry"]:
        title = text(item, ("title",))
        link = text(item, ("link",))
        if not link:
            for node in item.iter():
                if node.tag.rsplit("}", 1)[-1] == "link" and node.attrib.get("href"):
                    link = node.attrib["href"]
                    break
        published = text(item, ("pubdate", "published", "updated"))
        if not title or not link:
            continue
        uid = hashlib.sha256(f"{source}|{link}".encode()).hexdigest()[:20]
        rows.append({
            "id": uid,
            "published_at_utc": normalized_time(published),
            "collected_at_utc": datetime.now(timezone.utc).isoformat(),
            "source": source,
            "source_tier": tier,
            "record_type": feed_type,
            "title": title,
            "url": link,
            "language": "zh" if any("\u4e00" <= c <= "\u9fff" for c in title) else "en",
            "classification_status": "unreviewed"
        })
    return rows


def google_news_url(query: str) -> str:
    return "https://news.google.com/rss/search?" + urllib.parse.urlencode({
        "q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"
    })


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="data/raw/news/news.jsonl")
    args = parser.parse_args()
    config = json.loads((ROOT / "config/news_sources.json").read_text(encoding="utf-8"))
    rows, errors = [], []
    jobs = []
    for source in config["official_feeds"]:
        jobs.append((source["name"], source["url"], source["tier"], "official"))
    for query in config["consensus_queries"]:
        jobs.append((f"Google News: {query}", google_news_url(query), 3, "market_commentary"))
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(fetch_xml, url): (name, tier, kind) for name, url, tier, kind in jobs}
        for future in as_completed(futures):
            name, tier, kind = futures[future]
            try:
                rows.extend(parse_feed(future.result(), name, tier, kind))
            except Exception as exc:  # one bad free source must not stop the update
                errors.append({"source": name, "error": str(exc)})

    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    existing = {}
    if output.exists():
        for line in output.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                existing[row["id"]] = row
    for row in rows:
        existing[row["id"]] = row
    ordered = sorted(existing.values(), key=lambda x: x.get("published_at_utc") or "", reverse=True)
    output.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in ordered) + "\n", encoding="utf-8")
    print(json.dumps({"records": len(ordered), "new_fetch": len(rows), "errors": errors}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
