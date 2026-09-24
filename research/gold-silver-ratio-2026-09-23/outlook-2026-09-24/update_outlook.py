from pathlib import Path
from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote,urlencode
import subprocess,json,hashlib
import numpy as np
import pandas as pd
R=Path(__file__).resolve().parent
S=R/'sources';S.mkdir(exist_ok=True)
jobs={}
for sym in ['GLD','SLV','GC=F','SI=F','DX-Y.NYB','^GSPC']:
 jobs[sym.replace('=','_').replace('^','')+'.json']='https://query1.finance.yahoo.com/v8/finance/chart/'+quote(sym,safe='')+'?'+urlencode({'range':'2y','interval':'1d'})
jobs['gvz.csv']='https://cdn.cboe.com/api/global/us_indices/daily_prices/GVZ_History.csv'
jobs['DFII10.csv']='https://fred.stlouisfed.org/graph/?id=DFII10&cosd=2025-08-01&coed=2026-09-23&fq=Daily&fam=avg&fgst=lin&fgsnd=2020-02-01&line_index=1&line_id=DFII10&cosd=2025-08-01&coed=2026-09-23&mode=fred&fgst=lin&fgsnd=2020-02-01'
# FRED's direct CSV endpoint, with dates explicitly fixed.
jobs['DFII10.csv']='https://fred.stlouisfed.org/graph/fredgraph.csv?id=DFII10&cosd=2025-08-01&coed=2026-09-23'
def fetch(item):
 name,url=item;p=S/name
 run=subprocess.run(['curl.exe','-L','--fail','--silent','--show-error','--max-time','25','-A','Mozilla/5.0','-o',str(p),url],capture_output=True)
 result={'file':name,'url':url,'fetched_utc':datetime.now(timezone.utc).isoformat()}
 if run.returncode:result['error']=run.stderr.decode(errors='replace')
 else:result.update(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
 return result
with ThreadPoolExecutor(max_workers=3) as pool:meta=list(pool.map(fetch,jobs.items()))
(R/'sources_metadata.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
summary={'cutoff_complete_daily':'2026-09-23','symbols':{},'failures':[x for x in meta if 'error' in x]}
for sym in ['GLD','SLV','GC=F','SI=F','DX-Y.NYB','^GSPC']:
 path=S/(sym.replace('=','_').replace('^','')+'.json')
 if not path.exists():continue
 obj=json.loads(path.read_text());a=obj['chart']['result'][0]
 prices=a['indicators'].get('adjclose',[{}])[0].get('adjclose',a['indicators']['quote'][0]['close'])
 p=pd.Series(prices,index=pd.to_datetime(a['timestamp'],unit='s',utc=True).tz_localize(None).normalize()).loc[:'2026-09-23'].dropna()
 p.to_csv(R/(sym.replace('=','_').replace('^','')+'_daily.csv'),header=['close'],index_label='date')
 last=p.iloc[-1];date=p.index[-1]
 rec={'last_date':str(date.date()),'last_price':last,'returns_pct':{},'moving_average':{},'volatility':{}}
 for months in [1,3,6,12]:
  prior=p.loc[:date-pd.DateOffset(months=months)]
  if len(prior):rec['returns_pct'][str(months)]={'start_date':str(prior.index[-1].date()),'pct':float(100*(last/prior.iloc[-1]-1))}
 for n in [20,60,120,200]:rec['moving_average'][str(n)]={'level':float(p.tail(n).mean()),'distance_pct':float(100*(last/p.tail(n).mean()-1))}
 ret=np.log(p).diff()
 for n in [20,60,126,252]:rec['volatility'][str(n)]=float(np.sqrt(252*ret.tail(n).pow(2).mean()))
 rec['last_20_high_close']=float(p.tail(20).max());rec['last_20_low_close']=float(p.tail(20).min())
 summary['symbols'][sym]=rec
if (S/'gvz.csv').exists():
 gvz=pd.read_csv(S/'gvz.csv');gvz['DATE']=pd.to_datetime(gvz.DATE);gvz=gvz[gvz.DATE<='2026-09-23']
 col='GVZ' if 'GVZ' in gvz else 'CLOSE'
 summary['gvz']={'date':str(gvz.DATE.iloc[-1].date()),'close':float(gvz[col].iloc[-1]),'past_20_median':float(gvz[col].tail(20).median())}
try:
 real=pd.read_csv(S/'DFII10.csv');real.iloc[:,0]=pd.to_datetime(real.iloc[:,0]);real.iloc[:,1]=pd.to_numeric(real.iloc[:,1],errors='coerce');real=real.dropna()
 summary['real_yield']={'date':str(pd.Timestamp(real.iloc[-1,0]).date()),'percent':float(real.iloc[-1,1]),'20obs_change_percentage_points':float(real.iloc[-1,1]-real.iloc[-21,1])}
except Exception as e:summary['real_yield_unavailable']=str(e)
g=pd.read_csv(R/'GLD_daily.csv',parse_dates=['date']).set_index('date').close
s=pd.read_csv(R/'SLV_daily.csv',parse_dates=['date']).set_index('date').close
q=(g/s).dropna();ql=np.log(q)
summary['relative_return']={str(months):float(100*(q.iloc[-1]/q.loc[:q.index[-1]-pd.DateOffset(months=months)].iloc[-1]-1)) for months in [1,3,6,12]}
v=ql.diff(5);mu=v.rolling(252).mean().shift(1);sd=v.rolling(252).std().shift(1)
summary['ratio_speed']={'date':str(q.index[-1].date()),'5day_log_change_pct':float(v.iloc[-1]*100),'past_only_z':float(((v-mu)/sd).iloc[-1]),'5day_acceleration_log_pp':float((v-v.shift(5)).iloc[-1]*100)}
# Illustrative horizon-end bands: flat log median and constant current annualized implied volatility.
# GVZ is a 30-day GLD option measure: longer horizons are explicit assumptions, NOT observed option term structure.
summary['quote_anchor']={'gold_usd_oz':4249.90,'silver_usd_oz':63.54,'date_time':'2026-09-24 06:18 America/New_York','source':'https://invest.alexlexington.com/spot-prices','status':'indicative OTC dealer quote snapshot, not execution price'}
summary['bands']=[]
for months in [1,3,6,12]:
 sigma=summary['gvz']['close']/100;z=1.2815515655446004;t=months/12;anchor=summary['quote_anchor']['gold_usd_oz']
 summary['bands'].append({'months':months,'sigma_used':sigma,'assumptions':'zero log drift, lognormal increments, unchanged current 30-day annualized implied volatility','unvalidated_model_central_mass':.8,
   'lower':float(anchor*np.exp(-z*sigma*np.sqrt(t))),'upper':float(anchor*np.exp(z*sigma*np.sqrt(t))),
   'lower_35vol':float(anchor*np.exp(-z*.35*np.sqrt(t))),'upper_35vol':float(anchor*np.exp(z*.35*np.sqrt(t)))})
(R/'outlook_snapshot.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps(summary,indent=2,ensure_ascii=False))
