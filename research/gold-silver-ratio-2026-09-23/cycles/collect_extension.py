"""Run only after rounds 1 and 2 are recorded; not an ex ante live experiment."""
from collect_inputs import get,ROOT
from urllib.parse import urlencode,quote
from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor
import json,hashlib

lock={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['研究协议.md','common.py','round1.py','round2.py','第一轮记录.md','第二轮记录.md']}
(ROOT/'model_lock_before_2026.json').write_text(json.dumps({'time':datetime.now(timezone.utc).isoformat(),'sha256':lock},indent=2),encoding='utf-8')
urls={}
for symbol in ['GLD','SLV','DX-Y.NYB','^GSPC','^VIX']:
 params={'period1':int(datetime(2006,1,1,tzinfo=timezone.utc).timestamp()),'period2':int(datetime(2026,9,23,tzinfo=timezone.utc).timestamp()),'interval':'1d','events':'history'}
 urls['extended_'+symbol+'.json']='https://query1.finance.yahoo.com/v8/finance/chart/'+quote(symbol,safe='')+'?'+urlencode(params)
with ThreadPoolExecutor(max_workers=3) as pool:res=list(pool.map(get,urls.items()))
(ROOT/'extension_metadata.json').write_text(json.dumps(res,indent=2),encoding='utf-8')
print(json.dumps(res,indent=2))
