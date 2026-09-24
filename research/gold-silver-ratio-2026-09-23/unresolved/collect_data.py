from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import urlencode
import json, hashlib, subprocess

ROOT = Path(__file__).resolve().parent
RAW = ROOT / 'sources'
RAW.mkdir(exist_ok=True)
jobs = {}
for sym in ['GLD', 'SLV', 'IAU', 'SIVR']:
    jobs[f'{sym}_hourly.json'] = f'https://query1.finance.yahoo.com/v8/finance/chart/{sym}?' + urlencode({'range': '2y', 'interval': '1h', 'includePrePost': 'false'})
jobs['ssrn_latest.html'] = 'https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7170627'
jobs['zenodo_step1.txt'] = 'https://zenodo.org/records/21282855/files/step1_gold.py?download=1'
jobs['price_discovery.pdf'] = 'https://www.researchgate.net/profile/Bertrand-Villeneuve/publication/391128136_Gold_standards_for_price_discovery_A_moving_picture/links/680b3974df0e3f544f4949d5/Gold-Standards-for-Price-Discovery-A-Moving-Picture.pdf'

def fetch(job):
    name, url = job
    path = RAW / name
    r = subprocess.run(['curl.exe', '-L', '--fail', '--silent', '--show-error', '--max-time', '35', '-A', 'Mozilla/5.0', '-o', str(path), url], capture_output=True)
    meta = {'file': name, 'url': url, 'downloaded_at': datetime.now(timezone.utc).isoformat()}
    if r.returncode:
        meta['error'] = r.stderr.decode(errors='replace')
        return meta
    body = path.read_bytes()
    meta.update(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
    if name.endswith('.json'):
        obj = json.loads(body)['chart']['result'][0]
        stamps = obj['timestamp']
        meta.update(symbol=obj['meta']['symbol'], rows=len(stamps), currency=obj['meta']['currency'], timezone=obj['meta']['exchangeTimezoneName'],
                    first=datetime.fromtimestamp(stamps[0], timezone.utc).isoformat(), last=datetime.fromtimestamp(stamps[-1], timezone.utc).isoformat())
    return meta

if __name__ == '__main__':
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(fetch, jobs.items()))
    results += [{'file': 'xau_hour_probe.bi5', 'url': 'https://datafeed.dukascopy.com/datafeed/XAUUSD/2025/00/BID_candles_hour_1.bi5', 'error': 'HTTP 429; no bulk download attempted'},
                {'file': 'xag_minute_probe.bi5', 'url': 'https://datafeed.dukascopy.com/datafeed/XAGUSD/2025/00/02/BID_candles_min_1.bi5', 'error': 'Connection timed out after 25 seconds'}]
    (ROOT / 'input_metadata.json').write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(results, indent=2, ensure_ascii=True))
