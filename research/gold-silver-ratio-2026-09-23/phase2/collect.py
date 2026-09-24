"""Download public, versioned research inputs; never treat an HTML challenge as data."""
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json, hashlib

ROOT=Path(__file__).resolve().parent
RAW=ROOT/'sources'
RAW.mkdir(exist_ok=True)
cot_params={'$select':'distinct market_and_exchange_names,cftc_contract_market_code,commodity_name',
            '$where':"commodity_name in ('GOLD','SILVER')",'$limit':100}
urls={
 'cot_contracts.json':'https://publicreporting.cftc.gov/resource/72hh-3qpy.json?'+urlencode(cot_params),
 'lbma_gold.json':'https://api.db.nomics.world/v22/series/LBMA/gold_D?'+urlencode({'observations':1,'limit':20}),
 'lbma_silver.json':'https://api.db.nomics.world/v22/series/LBMA/silver_D?'+urlencode({'observations':1,'limit':20}),
}
def get(item):
 name,url=item
 try:
  with urlopen(Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=40) as r:
   body=r.read(); ct=r.headers.get('Content-Type')
  obj=json.loads(body)
  (RAW/name).write_bytes(body)
  result={'file':name,'url':url,'downloaded_at':datetime.now(timezone.utc).isoformat(),
          'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest(),'content_type':ct}
  if isinstance(obj,list): result['sample']=obj[:15]
  else:
   result['keys']=list(obj)
   result['series']=[{k:d.get(k) for k in ['series_code','series_name','start_date','end_date','nb_observations']} for d in obj.get('series',{}).get('docs',[])]
  return result
 except Exception as e:return {'file':name,'url':url,'error':str(e)}
if __name__=='__main__':
 with ThreadPoolExecutor(max_workers=3) as pool: results=list(pool.map(get,urls.items()))
 (ROOT/'collection_metadata.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
 print(json.dumps(results,indent=2))
