from pathlib import Path
from urllib.parse import urlencode
from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor
import json, hashlib, subprocess

ROOT=Path(__file__).resolve().parent
RAW=ROOT/'sources'
fields=['report_date_as_yyyy_mm_dd','market_and_exchange_names','cftc_contract_market_code','contract_units','futonly_or_combined',
 'open_interest_all','m_money_positions_long_all','m_money_positions_short_all','m_money_positions_spread',
 'tot_rept_positions_long_all','tot_rept_positions_short','nonrept_positions_long_all','nonrept_positions_short_all']
params={'$select':','.join(fields),'$where':"cftc_contract_market_code in ('088691','084691') AND report_date_as_yyyy_mm_dd < '2026-01-01T00:00:00'",'$order':'report_date_as_yyyy_mm_dd,cftc_contract_market_code','$limit':5000}
urls={'cot_gold_silver.json':'https://publicreporting.cftc.gov/resource/72hh-3qpy.json?'+urlencode(params)}
for symbol in ['GLD','SLV']:
 params={'period1':int(datetime(2006,1,1,tzinfo=timezone.utc).timestamp()),'period2':int(datetime(2026,1,1,tzinfo=timezone.utc).timestamp()),'interval':'1d','events':'history'}
 urls['yahoo_'+symbol+'.json']='https://query1.finance.yahoo.com/v8/finance/chart/'+symbol+'?'+urlencode(params)
def get(item):
 name,url=item
 path=RAW/name
 r=subprocess.run(['curl.exe','-L','--fail','--silent','--show-error','--max-time','50','-A','Mozilla/5.0','-o',str(path),url],capture_output=True)
 if r.returncode:return {'file':name,'url':url,'error':r.stderr.decode(errors='replace')}
 body=path.read_bytes(); obj=json.loads(body)
 out={'file':name,'url':url,'downloaded_at':datetime.now(timezone.utc).isoformat(),'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}
 if isinstance(obj,list):out.update(rows=len(obj),first=obj[:1],last=obj[-1:])
 else:
  a=obj['chart']['result'][0]
  out.update(meta=a['meta'],rows=len(a.get('timestamp',[])),first=a['timestamp'][0],last=a['timestamp'][-1])
 return out
with ThreadPoolExecutor(max_workers=3) as pool: results=list(pool.map(get,urls.items()))
(ROOT/'input_metadata.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
print(json.dumps(results,indent=2))
