from pathlib import Path
from urllib.request import Request,urlopen
from concurrent.futures import ThreadPoolExecutor
import json
ROOT=Path(__file__).resolve().parent
RAW=ROOT/'sources'; RAW.mkdir(exist_ok=True)
urls={
 'cot_sample.json':'https://publicreporting.cftc.gov/resource/72hh-3qpy.json?$limit=1',
 'xauusd.csv':'https://stooq.com/q/d/l/?s=xauusd&d1=20060101&d2=20251231&i=d',
 'xagusd.csv':'https://stooq.com/q/d/l/?s=xagusd&d1=20060101&d2=20251231&i=d',
}
def get(item):
 name,url=item
 try:
  with urlopen(Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=35) as r: body=r.read(); ctype=r.headers.get('Content-Type')
  (RAW/name).write_bytes(body)
  return {'name':name,'url':url,'bytes':len(body),'type':ctype,'sample':body[:1100].decode(errors='replace')}
 except Exception as e:return {'name':name,'url':url,'error':str(e)}
with ThreadPoolExecutor(max_workers=3) as pool:
 results=list(pool.map(get,urls.items()))
print(json.dumps(results,indent=2))
(ROOT/'probe_results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
