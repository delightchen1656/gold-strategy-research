from pathlib import Path
from urllib.parse import urlencode,quote
from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor
import json,hashlib,subprocess,csv,io

ROOT=Path(__file__).resolve().parent
RAW=ROOT/'sources';RAW.mkdir(exist_ok=True)
fields=['report_date_as_yyyy_mm_dd','market_and_exchange_names','cftc_contract_market_code','contract_units','futonly_or_combined',
 'open_interest_all','m_money_positions_long_all','m_money_positions_short_all','m_money_positions_spread',
 'prod_merc_positions_long','prod_merc_positions_short','swap_positions_long_all','swap__positions_short_all','swap__positions_spread_all',
 'other_rept_positions_long','other_rept_positions_short','other_rept_positions_spread',
 'tot_rept_positions_long_all','tot_rept_positions_short','nonrept_positions_long_all','nonrept_positions_short_all']
params={'$select':','.join(fields),'$where':"cftc_contract_market_code in ('088691','084691') AND report_date_as_yyyy_mm_dd < '2026-01-01T00:00:00'",'$order':'report_date_as_yyyy_mm_dd,cftc_contract_market_code','$limit':5000}
urls={'cot_full_2025.json':'https://publicreporting.cftc.gov/resource/72hh-3qpy.json?'+urlencode(params),
 'gvz.csv':'https://cdn.cboe.com/api/global/us_indices/daily_prices/GVZ_History.csv',
 'cftc_announcements.html':'https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalSpecialAnnouncements/index.htm'}
# Through 2025 only: 2026 is not fetched or evaluated until the third round.
for symbol in ['IAU','SIVR','GC=F','SI=F']:
 params={'period1':int(datetime(2006,1,1,tzinfo=timezone.utc).timestamp()),'period2':int(datetime(2026,1,1,tzinfo=timezone.utc).timestamp()),'interval':'1d','events':'history'}
 urls['yahoo_'+symbol.replace('=','_')+'_2025.json']='https://query1.finance.yahoo.com/v8/finance/chart/'+quote(symbol,safe='')+'?'+urlencode(params)
def get(item):
 name,url=item;path=RAW/name
 r=subprocess.run(['curl.exe','-L','--fail','--silent','--show-error','--max-time','40','-A','Mozilla/5.0','-o',str(path),url],capture_output=True)
 if r.returncode:return {'file':name,'url':url,'error':r.stderr.decode(errors='replace')}
 body=path.read_bytes()
 out={'file':name,'url':url,'downloaded_at':datetime.now(timezone.utc).isoformat(),'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}
 if name.endswith('.json'):
  obj=json.loads(body)
  if isinstance(obj,list):out.update(rows=len(obj),first_date=obj[0]['report_date_as_yyyy_mm_dd'],last_date=obj[-1]['report_date_as_yyyy_mm_dd'])
  else:
   a=obj['chart']['result'][0]
   out.update(symbol=a['meta']['symbol'],currency=a['meta']['currency'],exchange=a['meta']['exchangeName'],rows=len(a.get('timestamp',[])),events=a.get('events',{}))
 elif name.endswith('.csv'):
  rows=list(csv.DictReader(io.StringIO(body.decode('utf-8-sig'))));out.update(rows=len(rows),columns=list(rows[0]))
 return out
if __name__=='__main__':
 with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(get,urls.items()))
 (ROOT/'input_metadata.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
 print(json.dumps(results,indent=2))
