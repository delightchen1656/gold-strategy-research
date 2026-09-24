"""Fixed study utilities. No execution at import, no automatic parameter search."""
from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent
PREV=ROOT.parent/'phase2'
SEED=20260923

def json_save(name,obj):
 (ROOT/name).write_text(json.dumps(obj,indent=2,ensure_ascii=False,default=str),encoding='utf-8')

def yahoo_series(path,symbol):
 raw=json.loads(path.read_text())['chart']['result'][0]
 dates=pd.to_datetime(raw['timestamp'],unit='s',utc=True).tz_localize(None).normalize()
 a=pd.Series(raw['indicators']['adjclose'][0]['adjclose'],index=dates,name=symbol)
 assert a.index.is_unique and a.index.is_monotonic_increasing
 a=a.dropna();assert (a>0).all()
 return a

def prices_pair(pair='GLD_SLV',cutoff='2025-12-31',extended=False):
 syms={'GLD_SLV':['GLD','SLV'],'IAU_SIVR':['IAU','SIVR'],'GC_SI':['GC=F','SI=F']}[pair]
 out=[]
 for sym in syms:
  if extended:path=ROOT/'sources'/('extended_'+sym.replace('=','_')+'.json')
  elif sym in ['GLD','SLV']:path=PREV/'sources'/f'yahoo_{sym}.json'
  else:path=ROOT/'sources'/('yahoo_'+sym.replace('=','_')+'_2025.json')
  out.append(yahoo_series(path,sym))
 p=pd.concat(out,axis=1,join='inner').loc[:cutoff]
 p.columns=['gold','silver'];p.index.name='date'
 return p

def align(series,index,max_age=5):
 s=series.dropna().sort_index()
 union=s.index.union(index)
 v=s.reindex(union).ffill().reindex(index)
 stamp=pd.Series(s.index,index=s.index).reindex(union).ffill().reindex(index)
 v[(index-stamp).dt.days>max_age]=np.nan
 return v

def macro_panel(index,extended=False):
 result=pd.DataFrame(index=index)
 for key,col in [('dollar','close'),('sp500','close'),('vix','value'),('real','value')]:
  path=PREV/'sources'/f'{key}_snapshot.csv'
  s=pd.read_csv(path,parse_dates=['date']).set_index('date')[col]
  s=pd.to_numeric(s,errors='coerce')
  if extended and key in ['dollar','sp500']:
   sym={'dollar':'DX-Y.NYB','sp500':'^GSPC'}[key]
   new=yahoo_series(ROOT/'sources'/('extended_'+sym+'.json'),key)
   s=pd.concat([s.loc[:'2025-12-31'],new.loc['2026-01-01':]])
  if extended and key=='vix':
   new=yahoo_series(ROOT/'sources'/'extended_^VIX.json',key)
   s=pd.concat([s.loc[:'2025-12-31'],new.loc['2026-01-01':]])
  result[key]=align(s,index)
 gvz=pd.read_csv(ROOT/'sources'/'gvz.csv',parse_dates=['DATE']).set_index('DATE').GVZ
 result['gvz']=align(gvz,index)
 return result

def make_panel(pair='GLD_SLV',cutoff='2025-12-31',extended=False):
 p=prices_pair(pair,cutoff,extended)
 m=macro_panel(p.index,extended)
 lg,ls=np.log(p.gold),np.log(p.silver);q=lg-ls
 rg,rs,rq=lg.diff(),ls.diff(),q.diff()
 d=p.copy();d['log_ratio']=q
 for h in [5,20,60]:
  d[f'gvol{h}']=np.log(np.sqrt(rg.pow(2).rolling(h).mean()*252))
 for h in [5,20]:
  d[f'gret{h}']=lg.diff(h);d[f'sret{h}']=ls.diff(h);d[f'qret{h}']=q.diff(h)
 d['qaccel']=d.qret5-d.qret5.shift(5)
 d['qz']=(d.qret5-d.qret5.rolling(252).mean().shift(1))/d.qret5.rolling(252).std().shift(1)
 d['qabs']=d.qz.abs()
 d['qvol20']=np.log(np.sqrt(rq.pow(2).rolling(20).mean()*252))
 for key in ['vix','gvz']:d['log_'+key]=np.log(m[key]).shift(1)
 d['dollar20']=np.log(m.dollar).diff(20).shift(1)
 d['real20']=m.real.diff(20).shift(1)
 d['sp20']=np.log(m.sp500).diff(20).shift(1)
 # Daily cross-market surprise, coefficients estimated strictly before each observation.
 factors=pd.DataFrame({'gold':rg,'dollar':np.log(m.dollar).diff(),'stocks':np.log(m.sp500).diff()})
 residual=pd.Series(np.nan,index=p.index);sigma=residual.copy()
 for i in range(253,len(p)):
  x0=factors.iloc[i-252:i].to_numpy();y0=rq.iloc[i-252:i].to_numpy();xnow=factors.iloc[i].to_numpy()
  if not np.isfinite(np.r_[x0.ravel(),y0,xnow]).all():continue
  x=np.column_stack([np.ones(252),x0]);coef=np.linalg.lstsq(x,y0,rcond=None)[0]
  residual.iloc[i]=rq.iloc[i]-np.r_[1.,xnow]@coef
  sigma.iloc[i]=np.sqrt(np.mean((y0-x@coef)**2))
 d['surprise5']=residual.rolling(5).sum()/np.sqrt(sigma.pow(2).rolling(5).sum())
 d['surprise_abs']=d.surprise5.abs()
 d['surprise_up']=d.surprise5.clip(lower=0)
 d['surprise_down']=(-d.surprise5).clip(lower=0)
 for h in [5,20]:
  d[f'future_vol{h}']=np.log(np.sqrt(rg.pow(2).rolling(h).mean().shift(-(h+1))*252))
  d[f'future_silver_vol{h}']=np.log(np.sqrt(rs.pow(2).rolling(h).mean().shift(-(h+1))*252))
  d[f'future_return{h}']=lg.shift(-(h+1))-lg.shift(-1)
  d[f'future_ratio{h}']=q.shift(-(h+1))-q.shift(-1)
  d[f'end{h}']=pd.Series(d.index,index=d.index).shift(-(h+1))
 d['vix_change5']=np.log(m.vix).diff(5)
 d['gvz_change5']=np.log(m.gvz).diff(5)
 d['sp_change5']=np.log(m.sp500).diff(5)
 return d

GOLD=['gvol5','gvol20','gvol60','gret5','gret20']
MACRO=GOLD+['log_vix','dollar20','real20','sp20']
STRONG=MACRO+['log_gvz']
FEATURES={'speed':['qret5','qret20'],'acceleration':['qaccel'],'raw_shock':['qabs'],
          'residual_shock':['surprise_abs'],'asymmetric_shock':['surprise_up','surprise_down']}

def risk_models():
 models={'macro':MACRO,'gvz':STRONG}
 for name,f in FEATURES.items():models[name]=STRONG+f
 return models

def predict(frame,target,end_col,models,start='2012-01-01',stop='2099-12-31',window_years=None,min_years=5,min_obs=240):
 columns=list(dict.fromkeys(k for cs in models.values() for k in cs))
 data=frame[columns+[target,end_col]].dropna().copy()
 predictions=[]
 for dt,row in data.loc[start:stop].iterrows():
  train=data[(data.index<dt)&(data[end_col]<=dt)]
  if len(train)<min_obs or (dt-data.index[0]).days<365.25*min_years:continue
  if window_years is not None:train=train.loc[dt-pd.DateOffset(years=window_years):]
  if len(train)<min(200,min_obs):continue
  assert train[end_col].max()<=dt
  for model,cols in models.items():
   raw=train[cols].to_numpy(float); mu=raw.mean(0);sd=raw.std(0);sd[sd<1e-10]=1
   x=np.column_stack([np.ones(len(train)),(raw-mu)/sd])
   b=np.linalg.lstsq(x,train[target].to_numpy(float),rcond=None)[0]
   value=np.r_[1.,(row[cols].to_numpy(float)-mu)/sd]@b
   predictions.append({'date':str(dt.date()),'target':target,'model':model,'actual':float(row[target]),'forecast':float(value),
    'training_n':len(train),'latest_training_label':str(train[end_col].max().date()),'label_end':str(row[end_col].date())})
 return pd.DataFrame(predictions)

def error_stats(a,b,B=4000,block=13):
 e0=np.asarray(a,float);e1=np.asarray(b,float);n=len(e0)
 out={'mse_change_pct':float(100*(e1.mean()/e0.mean()-1)),'base_mse':float(e0.mean()),'extended_mse':float(e1.mean())}
 if n<40:
  out['interval_note']='Short evaluation; no dependence-adjusted interval claimed.';return out
 rng=np.random.default_rng(SEED);block=min(block,n//3)
 ix=(rng.integers(0,n-block+1,size=(B,int(np.ceil(n/block))))[:,:,None]+np.arange(block)).reshape(B,-1)[:,:n]
 boot=100*(e1[ix].mean(axis=1)/e0[ix].mean(axis=1)-1)
 out['ci95_pct']=[float(v) for v in np.quantile(boot,[.025,.975])]
 advantage=e0-e1;centered=advantage-advantage.mean()
 out['improvement_p_one_sided']=float((1+np.sum(centered[ix].mean(axis=1)>=advantage.mean()))/(B+1))
 return out

def compare(pred,comparisons,periods=None):
 if periods is None:periods=[('all','1900','2099'),('early','1900','2018-12-31'),('recent','2019','2025-12-31')]
 results=[]
 for target,part in pred.groupby('target'):
  for label,start,end in periods:
   p=part[(part.date>=start)&(part.date<=end)]
   if p.empty:continue
   wide=p.pivot(index='date',columns='model',values='forecast');actual=p.groupby('date').actual.first()
   for base,model in comparisons:
    if base not in wide or model not in wide:continue
    valid=wide[[base,model]].dropna();y=actual.loc[valid.index]
    r={'target':target,'period':label,'baseline':base,'model':model,'n':len(valid),'first':valid.index[0],'last':valid.index[-1]}
    r.update(error_stats((valid[base]-y)**2,(valid[model]-y)**2));results.append(r)
 return results

def holm_adjust(results,filter_fn):
 group=[r for r in results if filter_fn(r) and 'improvement_p_one_sided' in r]
 group.sort(key=lambda r:r['improvement_p_one_sided']);maximum=0
 for i,r in enumerate(group):
  maximum=max(maximum,(len(group)-i)*r['improvement_p_one_sided'])
  r['holm_p']=float(min(1,maximum));r['holm_family_size']=len(group)

def weekly(panel):
 result=panel.groupby(panel.index.to_period('W-FRI')).tail(1)
 # Exclude a final unfinished calendar week at the end of a download window.
 return result[result.index.to_period('W-FRI').end_time.normalize()<=panel.index.max()]
