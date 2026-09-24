"""Exploratory expanding-window studies. COT clock = position date, NOT public release."""
from pathlib import Path
import json, hashlib
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent
PROJECT=ROOT.parents[2]
RAW=ROOT/'sources'
SEED=20260923
audit={}

def load_price(symbol):
 obj=json.loads((RAW/f'yahoo_{symbol}.json').read_text())['chart']['result'][0]
 dates=pd.to_datetime(obj['timestamp'],unit='s',utc=True).tz_convert('America/New_York').tz_localize(None).normalize()
 q=obj['indicators']['quote'][0]
 x=pd.DataFrame({'close':q['close'],'adjusted':obj['indicators']['adjclose'][0]['adjclose'],'volume':q['volume']},index=dates)
 assert x.index.is_unique and x.index.is_monotonic_increasing
 audit[symbol]={'raw_n':len(x),'missing':int(x.adjusted.isna().sum()),'events':obj.get('events',{}),'max_close_adj_gap':float((x.close/x.adjusted-1).abs().max())}
 x=x.dropna(subset=['adjusted'])
 assert (x.adjusted>0).all()
 return x.adjusted.rename(symbol)

prices=pd.concat([load_price('GLD'),load_price('SLV')],axis=1,join='inner')
prices.index.name='date'
prices.to_csv(ROOT/'daily_etf_prices.csv')
audit['daily']={'n':len(prices),'first':str(prices.index[0].date()),'last':str(prices.index[-1].date()),'max_gap_days':int(prices.index.to_series().diff().dt.days.max())}
logs=np.log(prices)
r=logs.diff()
for sym in prices:
 audit[sym]['largest_daily_moves']={str(k.date()):float(v) for k,v in r[sym].abs().nlargest(5).items()}
wb=pd.read_csv(ROOT.parent/'gold_silver_monthly.csv',parse_dates=['date']).set_index('date')
monthly=prices.resample('MS').mean().loc['2006-05':]
cross=pd.DataFrame({'proxy':monthly.GLD/monthly.SLV,'worldbank':wb.ratio}).dropna()
delta=np.log(cross).diff().dropna()
audit['monthly_crosscheck']={'n_changes':len(delta),'log_change_correlation':float(delta.proxy.corr(delta.worldbank)),
 'log_change_difference_rmse':float(np.sqrt(np.mean((delta.proxy-delta.worldbank)**2))),
 'note':'Ratio of monthly average ETF prices vs World Bank ratio of monthly averages; excludes partial April 2006; levels are not comparable.'}
cross.to_csv(ROOT/'monthly_proxy_crosscheck.csv')

# Snapshot existing macro inputs, so later project data refreshes do not alter reproduction.
macro_files={'dollar':('market/yahoo_dollar_index.csv','close'),'vix':('macro/fred_vix_close.csv','value'),
             'real':('macro/fred_us_10y_real_yield.csv','value'),'sp500':('market/yahoo_sp500.csv','close')}
for name,(rel,col) in macro_files.items():
 dst=RAW/(name+'_snapshot.csv')
 if not dst.exists():dst.write_bytes((PROJECT/'data/raw'/rel).read_bytes())
 m=pd.read_csv(dst,parse_dates=['date']).set_index('date')[col]
 m=pd.to_numeric(m,errors='coerce').dropna()
 # backward-only join, no fills more than five calendar days old
 aligned=m.reindex(m.index.union(prices.index)).sort_index().ffill().reindex(prices.index)
 last=pd.Series(m.index,index=m.index).reindex(m.index.union(prices.index)).ffill().reindex(prices.index)
 aligned[(prices.index-last).dt.days>5]=np.nan
 prices[name]=aligned
 audit[name]={'source_file':rel,'snapshot_sha256':hashlib.sha256(dst.read_bytes()).hexdigest(),'missing_aligned':int(aligned.isna().sum())}

d=pd.DataFrame(index=prices.index)
lg,ls=np.log(prices.GLD),np.log(prices.SLV)
lq=lg-ls
rg,rs,rq=lg.diff(),ls.diff(),lq.diff()
for h in [5,20,60]:d[f'log_gvol{h}']=np.log(np.sqrt(rg.pow(2).rolling(h).mean()*252))
for h in [5,20]:
 d[f'gret{h}']=lg.diff(h)
 d[f'qret{h}']=lq.diff(h)
d['qaccel']=d.qret5-d.qret5.shift(5)
d['log_qvol20']=np.log(np.sqrt(rq.pow(2).rolling(20).mean()*252))
d['qz5']=(d.qret5-d.qret5.rolling(252).mean().shift(1))/d.qret5.rolling(252).std().shift(1)
d['qshock']=d.qz5.abs()
d['log_vix']=np.log(prices.vix).shift(1)
d['dollar20']=np.log(prices.dollar).diff(20).shift(1)
d['real20']=prices.real.diff(20).shift(1)
d['signal_date']=d.index
# At t, t+1 is the skipped trading day; returns t+2 ... t+21 cover 20 days.
d['log_future_vol']=np.log(np.sqrt(rg.pow(2).rolling(20).mean().shift(-21)*252))
d['future_return']=lg.shift(-21)-lg.shift(-1)
d['log_future_downside']=np.log(np.sqrt(rg.clip(upper=0).pow(2).rolling(20).mean().shift(-21)*252)+1e-8)
d['label_end']=pd.Series(d.index,index=d.index).shift(-21)
weekly=d.groupby(d.index.to_period('W-FRI')).tail(1).copy()

base=['log_gvol5','log_gvol20','log_gvol60','gret5','gret20']
extras={'speed':['qret5','qret20'],'acceleration':['qaccel'],'ratio_volatility':['log_qvol20'],'unusual_move':['qshock']}
macro=['log_vix','dollar20','real20']
models={'gold_history':base,'gold_and_macro':base+macro}
for k,x in extras.items():
 models['gold_plus_'+k]=base+x
 models['macro_plus_'+k]=base+macro+x

def forecasts(frame,target,model_map,start='2012-01-01',train_start=None):
 cols=list(dict.fromkeys(c for x in model_map.values() for c in x))
 a=frame[cols+[target,'label_end']].dropna().copy()
 if train_start is not None:a=a.loc[train_start:]
 out=[]
 for dt,row in a.loc[start:].iterrows():
  tr=a.loc[a.label_end<=dt]
  # labels must have concluded by signal time, and signal dates must be strictly earlier.
  assert (tr.index<dt).all()
  if len(tr)<240 or (dt-tr.index[0]).days<365.25*5:continue
  for name,columns in model_map.items():
   raw=tr[columns].to_numpy(float)
   mean=raw.mean(axis=0); sd=raw.std(axis=0); sd[sd<1e-10]=1
   x=np.column_stack([np.ones(len(tr)),(raw-mean)/sd])
   beta=np.linalg.lstsq(x,tr[target].to_numpy(float),rcond=None)[0]
   yhat=np.r_[1.,(row[columns].to_numpy(float)-mean)/sd]@beta
   out.append({'date':str(dt.date()),'target':target,'model':name,'actual':float(row[target]),'forecast':float(yhat),
               'training_n':len(tr),'latest_training_label':str(tr.label_end.max().date()),'label_end':str(row.label_end.date())})
 return pd.DataFrame(out)

def boot_interval(e0,e1,block=13,B=2000):
 n=len(e0); rng=np.random.default_rng(SEED)
 # Non-circular moving blocks; weekly dependence and overlapping outcomes are retained within blocks.
 starts=rng.integers(0,n-block+1,size=(B,int(np.ceil(n/block))))
 idx=(starts[:,:,None]+np.arange(block)).reshape(B,-1)[:,:n]
 values=100*(e1[idx].mean(axis=1)/e0[idx].mean(axis=1)-1)
 return [float(v) for v in np.quantile(values,[.025,.975])]

def summarize(pred, comparisons):
 results=[]
 for target,pp in pred.groupby('target'):
  for period,start,end in [('all','1900','2099'),('2012-2018','2012','2018-12-31'),('2019-2025','2019','2025-12-31')]:
   p=pp[(pp.date>=start)&(pp.date<=end)]
   if p.empty:continue
   wide=p.pivot(index='date',columns='model',values='forecast')
   actual=p.groupby('date').actual.first()
   for b,m in comparisons:
    if b not in wide or m not in wide:continue
    e0=(wide[b].to_numpy()-actual.to_numpy())**2
    e1=(wide[m].to_numpy()-actual.to_numpy())**2
    result={'target':target,'period':period,'baseline':b,'model':m,'n':len(actual),'first':wide.index[0],'last':wide.index[-1],
      'baseline_mse':float(e0.mean()),'model_mse':float(e1.mean()),'mse_change_percent':float(100*(e1.mean()/e0.mean()-1))}
    if len(actual)>=26:result['block_bootstrap_95_percent']=boot_interval(e0,e1)
    results.append(result)
 return results

riskpred=pd.concat([forecasts(weekly,t,models) for t in ['log_future_vol','future_return','log_future_downside']],ignore_index=True)
riskpred.to_csv(ROOT/'risk_predictions.csv',index=False)
risk_comparisons=[('gold_history','gold_and_macro')]+[('gold_history','gold_plus_'+k) for k in extras]+[('gold_and_macro','macro_plus_'+k) for k in extras]
risk_results=summarize(riskpred,risk_comparisons)

# Descriptive contemporaneous relationships, not forward sentiment predictions.
sent=pd.DataFrame({'q5':lq.diff(5),'g5':lg.diff(5),'s5':ls.diff(5),'sp500_5':np.log(prices.sp500).diff(5),
 'vix5':np.log(prices.vix).diff(5),'qz5':d.qz5,'future_vol':np.exp(d.log_future_vol)})
sent=sent.loc[weekly.index].dropna()
sentiment={'n':len(sent),'correlations':sent[['q5','g5','s5','sp500_5','vix5']].corr().round(6).to_dict()}

# COT futures-only, exchange and units verified directly from the public API.
cot=pd.DataFrame(json.loads((RAW/'cot_gold_silver.json').read_text()))
cot['date']=pd.to_datetime(cot.report_date_as_yyyy_mm_dd)
assert not cot.duplicated(['date','cftc_contract_market_code']).any()
num=[x for x in cot.columns if x not in ['report_date_as_yyyy_mm_dd','market_and_exchange_names','cftc_contract_market_code','contract_units','futonly_or_combined','date']]
cot[num]=cot[num].apply(pd.to_numeric,errors='raise')
assert not cot[num].isna().any().any()
assert (cot[num]>=0).all().all()
assert (cot.tot_rept_positions_long_all+cot.nonrept_positions_long_all==cot.open_interest_all).all()
assert (cot.tot_rept_positions_short+cot.nonrept_positions_short_all==cot.open_interest_all).all()
assert cot.futonly_or_combined.eq('FutOnly').all()
w=None
for code,metal in [('088691','gold'),('084691','silver')]:
 a=cot[cot.cftc_contract_market_code==code].set_index('date').sort_index()
 z=pd.DataFrame(index=a.index)
 z[metal+'_net']=(a.m_money_positions_long_all-a.m_money_positions_short_all)/a.open_interest_all
 z[metal+'_long']=a.m_money_positions_long_all/a.open_interest_all
 z[metal+'_short']=a.m_money_positions_short_all/a.open_interest_all
 z[metal+'_net_contracts']=a.m_money_positions_long_all-a.m_money_positions_short_all
 z[metal+'_oi']=a.open_interest_all
 z[metal+'_change']=z[metal+'_net'].diff()
 z[metal+'_contracts_change_scaled']=z[metal+'_net_contracts'].diff()/a.open_interest_all.shift(1)
 w=z if w is None else w.join(z,how='inner')
w=w.sort_index()
px=prices[['GLD','SLV']].reindex(prices.index.union(w.index)).sort_index().ffill().reindex(w.index)
price_dates=pd.Series(prices.index,index=prices.index).reindex(prices.index.union(w.index)).sort_index().ffill().reindex(w.index)
assert ((w.index-price_dates).dt.days<=4).all()
w['price_date']=price_dates
wg,ws=np.log(px.GLD),np.log(px.SLV); wq=wg-ws
for h in [1,4]:
 w[f'gold_return{h}']=wg.diff(h)
 w[f'ratio_return{h}']=wq.diff(h)
w['silver_return1']=ws.diff()
w['relative_position_change']=w.gold_change-w.silver_change
for metal in ['gold','silver']:
 for lag in range(4):w[f'{metal}_change_lag{lag}']=w[metal+'_change'].shift(lag)
audit['cot']={'n_each':len(w),'first':str(w.index[0].date()),'last':str(w.index[-1].date()),
 'date_spacing_counts':{str(k):int(v) for k,v in w.index.to_series().diff().dt.days.value_counts().items()},
 'weekdays':{str(k):int(v) for k,v in w.index.day_name().value_counts().items()},
 'nonmatching_price_dates':int((w.index!=w.price_date).sum()),'all_position_balance_checks_passed':True,
 'publication_clock':'position_date only; no complete historical release timestamp archive; not a tradable COT backtest'}
lead=[]
for period,start,end in [('all','2006','2025-12-31'),('2012-2018','2012','2018-12-31'),('2019-2025','2019','2025-12-31')]:
 for k in [-4,-1,0,1,4]:
  for col in ['gold_change','silver_change','relative_position_change']:
   a=pd.concat([w.ratio_return1.rename('q'),w[col].shift(-k).rename('p')],axis=1).loc[start:end].dropna()
   lead.append({'period':period,'position_shift_weeks':k,'position':col,'n':len(a),'correlation':float(a.q.corr(a.p))})
own_correlations={metal:{'share_change':float(w[f'{metal}_return1'].corr(w[metal+'_change'])),
                       'contracts_change_scaled':float(w[f'{metal}_return1'].corr(w[metal+'_contracts_change_scaled']))} for metal in ['gold','silver']}
cotpred=[]; cotcomparisons=[('base','plus_ratio'),('base','plus_positions')]
for h in [1,4]:
 w['label_end']=pd.Series(w.index,index=w.index).shift(-h)
 for metal in ['gold','silver']:
  target=f'future_{metal}_position_{h}w'
  w[target]=w[metal+'_net'].shift(-h)-w[metal+'_net']
  b=[f'{metal}_change_lag{k}' for k in range(4)]+[metal+'_net','gold_return1','gold_return4']
  mm={'base':b,'plus_ratio':b+['ratio_return1','ratio_return4']}
  for label,cut in [('all_history',None),('post_public_launch','2009-09-01')]:
   p=forecasts(w,target,mm,train_start=cut);p['training_variant']=label;cotpred.append(p)
 for kind,series in [('gold_return',wg),('ratio_return',wq)]:
  target=f'future_{kind}_{h}w'
  w[target]=series.shift(-h)-series
  b=['gold_return1','gold_return4','ratio_return1','ratio_return4']
  mm={'base':b,'plus_positions':b+['gold_net','silver_net','gold_change','silver_change']}
  for label,cut in [('all_history',None),('post_public_launch','2009-09-01')]:
   p=forecasts(w,target,mm,train_start=cut);p['training_variant']=label;cotpred.append(p)
cotpred=pd.concat(cotpred,ignore_index=True)
cotpred.to_csv(ROOT/'cot_predictions.csv',index=False)
cot_results=[]
for variant,p in cotpred.groupby('training_variant'):
 for z in summarize(p,cotcomparisons):z['training_variant']=variant;cot_results.append(z)
w.to_csv(ROOT/'weekly_cot_panel.csv')
weekly.to_csv(ROOT/'weekly_risk_panel.csv')
out={'audit':audit,'risk_results':risk_results,'sentiment':sentiment,'cot_lead_lag':lead,
     'own_price_position_correlations':own_correlations,'cot_results':cot_results,
     'method':{'seed':SEED,'bootstrap_repetitions':2000,'block_weeks':13,'positive_mse_change':'worse than baseline',
               'multiple_testing':'unadjusted exploratory intervals','proxy':'GLD/SLV adjusted NYSE Arca close; NOT spot ratio levels'}}
(ROOT/'results.json').write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps({'audit':audit,'risk_vol_all':[x for x in risk_results if x['target']=='log_future_vol' and x['period']=='all'],
 'cot_all':[x for x in cot_results if x['period']=='all'],'own_correlations':own_correlations},indent=2,ensure_ascii=False))
