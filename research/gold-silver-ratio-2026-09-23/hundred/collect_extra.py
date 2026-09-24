from utils import *
from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlencode,quote
import subprocess,hashlib,shutil

raw=ROOT/'sources';raw.mkdir(exist_ok=True)
jobs={}
for symbol in ['HG=F','BZ=F']:
    params={'period1':1136073600,'period2':1767225600,'interval':'1d'}
    jobs[symbol.replace('=','_')+'.json']='https://query1.finance.yahoo.com/v8/finance/chart/'+quote(symbol,safe='')+'?'+urlencode(params)
for symbol in ['GLD','SLV','IAU','SIVR']:
    jobs[symbol+'_daily.json']='https://query1.finance.yahoo.com/v8/finance/chart/'+symbol+'?'+urlencode({'range':'2y','interval':'1d'})
def fetch(item):
    name,url=item;p=raw/name
    if p.exists():return {'file':name,'url':url,'cached':True,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}
    r=subprocess.run(['curl.exe','-L','--fail','--silent','--show-error','--max-time','30','-A','Mozilla/5.0','-o',str(p),url],capture_output=True)
    row={'file':name,'url':url,'downloaded_at':datetime.now(timezone.utc).isoformat()}
    if r.returncode:row['error']=r.stderr.decode(errors='replace')
    else:row.update(sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size)
    return row
with ThreadPoolExecutor(max_workers=2) as pool:rows=list(pool.map(fetch,jobs.items()))
origin=ROOT.parents[2]/'data/raw/macro/fred_us_10y_breakeven_inflation.csv'
dest=raw/'breakeven_snapshot.csv';shutil.copyfile(origin,dest)
rows.append({'file':dest.name,'source_local':str(origin),'source_series':'FRED T10YIE','source_url':'https://fred.stlouisfed.org/series/T10YIE','sha256':hashlib.sha256(dest.read_bytes()).hexdigest()})
save('extra_input_metadata.json',rows)
print(json.dumps(rows,indent=2))
