from common import *

raw=pd.DataFrame(json.loads((ROOT/'sources/cot_full_2025.json').read_text()))
raw['date']=pd.to_datetime(raw.report_date_as_yyyy_mm_dd)
meta=['report_date_as_yyyy_mm_dd','market_and_exchange_names','cftc_contract_market_code','contract_units','futonly_or_combined','date']
numeric=[c for c in raw if c not in meta];raw[numeric]=raw[numeric].apply(pd.to_numeric,errors='raise')
assert not raw.duplicated(['date','cftc_contract_market_code']).any()
assert (raw[numeric]>=0).all().all() and (raw.open_interest_all>0).all()
assert (raw.tot_rept_positions_long_all+raw.nonrept_positions_long_all==raw.open_interest_all).all()
assert (raw.tot_rept_positions_short+raw.nonrept_positions_short_all==raw.open_interest_all).all()
w=None
groups={'mm':('m_money_positions_long_all','m_money_positions_short_all'),
        'producer':('prod_merc_positions_long','prod_merc_positions_short'),
        'swap':('swap_positions_long_all','swap__positions_short_all'),
        'other':('other_rept_positions_long','other_rept_positions_short')}
for code,metal in [('088691','g'),('084691','s')]:
 a=raw[raw.cftc_contract_market_code==code].set_index('date').sort_index();z=pd.DataFrame(index=a.index)
 z[metal+'_oi']=a.open_interest_all
 for group,(long_col,short_col) in groups.items():
  z[f'{metal}_{group}_net']=(a[long_col]-a[short_col])/a.open_interest_all
  z[f'{metal}_{group}_net_delta']=(a[long_col].diff()-a[short_col].diff())/a.open_interest_all.shift(1)
 for side,col in [('long','m_money_positions_long_all'),('short','m_money_positions_short_all')]:
  z[f'{metal}_{side}_contracts']=a[col]
  z[f'{metal}_{side}_level']=a[col]/a.open_interest_all
  z[f'{metal}_{side}_delta']=a[col].diff()/a.open_interest_all.shift(1)
  for lag in range(4):z[f'{metal}_{side}_lag{lag}']=z[f'{metal}_{side}_delta'].shift(lag)
 z[metal+'_net_contracts']=a.m_money_positions_long_all-a.m_money_positions_short_all
 for lag in range(4):z[f'{metal}_net_lag{lag}']=z[f'{metal}_mm_net_delta'].shift(lag)
 rank=z[metal+'_mm_net'].rolling(157).apply(lambda v:np.mean(v[:-1]<=v[-1]),raw=True)
 z[metal+'_rank']=rank
 z[metal+'_tail']=(rank-.9).clip(lower=0)+(rank-.1).clip(upper=0)
 w=z if w is None else w.join(z,how='inner')

d=pd.read_csv(ROOT/'daily_primary_panel.csv',parse_dates=['date','end5','end20']).set_index('date')
lg=align(np.log(d.gold),w.index);ls=align(np.log(d.silver),w.index);q=lg-ls
for h in [1,4]:w[f'gret{h}']=lg.diff(h);w[f'sret{h}']=ls.diff(h);w[f'qret{h}']=q.diff(h)
w['qlevel_z']=(q-q.rolling(156).mean().shift(1))/q.rolling(156).std().shift(1)
for col in ['log_vix','log_gvz','dollar20','real20']:w[col]=align(d[col],w.index)

structural=[]
for metal in ['g','s']:
 for group in groups:
  for lag in [-1,0,1,4]:
   x=pd.concat([w[f'{metal}ret1'],w[f'{metal}_{group}_net_delta'].shift(-lag)],axis=1).dropna()
   structural.append({'metal':metal,'group':group,'position_shift_periods':lag,'n':len(x),'corr':float(x.iloc[:,0].corr(x.iloc[:,1]))})

# 2013, 2018/19, 2023, 2025: deliberately generous exclusion windows, not invented release dates.
blackouts=[('2013-10-01','2013-11-15'),('2018-12-22','2019-03-29'),('2023-02-01','2023-04-07'),('2025-10-01','2025-12-31')]
cot_features=['g_mm_net','s_mm_net','g_mm_net_delta','s_mm_net_delta',
 'g_long_delta','g_short_delta','s_long_delta','s_short_delta','g_tail','s_tail']
pr=weekly(d).copy()
clock_audit={};clock_predictions=[]
for clock,days in [('position_date',0),('delayed_10_days',10)]:
 z=w[cot_features].copy();z['cot_asof']=w.index
 z.index=z.index+pd.Timedelta(days=days);z.index.name='available_on'
 left=pr.reset_index().sort_values('date');right=z.reset_index().sort_values('available_on')
 a=pd.merge_asof(left,right,left_on='date',right_on='available_on',direction='backward').set_index('date')
 for start,end in blackouts:a.loc[start:end,cot_features]=np.nan
 age=(a.index-pd.to_datetime(a.cot_asof)).dt.days
 a.loc[age>24,cot_features]=np.nan
 b=STRONG+['qret5','qret20']
 mm={'base':b,'net_positions':b+['g_mm_net','s_mm_net','g_mm_net_delta','s_mm_net_delta'],
  'long_short_components':b+['g_mm_net','s_mm_net','g_long_delta','g_short_delta','s_long_delta','s_short_delta'],
  'extreme_positions':b+['g_tail','s_tail']}
 auditrows=a.dropna(subset=cot_features)
 assert ((auditrows.index-pd.to_datetime(auditrows.cot_asof)).dt.days>=days).all()
 clock_audit[clock]={'valid_feature_rows':len(auditrows),'min_position_age_days':float(age.loc[auditrows.index].min()),
   'max_position_age_days':float(age.loc[auditrows.index].max()),'first':str(auditrows.index[0].date()),'last':str(auditrows.index[-1].date())}
 for h in [5,20]:
  for target in ['future_return'+str(h),'future_ratio'+str(h)]:
   p=predict(a,target,'end'+str(h),mm)
   p['clock']=clock;clock_predictions.append(p)
 a.to_csv(ROOT/f'round2_price_panel_{clock}.csv')
pricepred=pd.concat(clock_predictions,ignore_index=True);pricepred.to_csv(ROOT/'round2_price_predictions.csv',index=False)
price_results=[]
for clock,p in pricepred.groupby('clock'):
 rr=compare(p,[('base','net_positions'),('base','long_short_components'),('base','extreme_positions')])
 for r in rr:r['clock']=clock
 price_results.extend(rr)
holm_adjust(price_results,lambda r:r['clock']=='delayed_10_days' and r['period']=='all')

# Price-to-position forecasts use positions at their reference date and are explicitly retrospective.
fund_predictions=[]
for h in [1,4]:
 w['end']=pd.Series(w.index,index=w.index).shift(-h)
 for metal in ['g','s']:
  for side in ['long','short','net']:
   target=f'future_{metal}_{side}_{h}w'
   w[target]=(w[f'{metal}_{side}_contracts'].shift(-h)-w[f'{metal}_{side}_contracts'])/w[metal+'_oi']
   level=metal+'_mm_net' if side=='net' else f'{metal}_{side}_level'
   base=[f'{metal}_{side}_lag{k}' for k in range(4)]+[level,'gret1','gret4','log_vix','log_gvz','dollar20','real20']
   mm={'base':base,'ratio_speed':base+['qret1','qret4'],'ratio_level':base+['qlevel_z']}
   p=predict(w,target,'end',mm);fund_predictions.append(p)
fundpred=pd.concat(fund_predictions,ignore_index=True);fundpred.to_csv(ROOT/'round2_fund_predictions.csv',index=False)
fund_results=compare(fundpred,[('base','ratio_speed'),('base','ratio_level')])
holm_adjust(fund_results,lambda r:r['period']=='all')
w.to_csv(ROOT/'round2_cot_panel.csv')

# Decompose net selling into long reduction and short additions, without pretending to see individual trades.
decomp=[]
for metal in ['g','s']:
 x=w[[metal+'_long_delta',metal+'_short_delta',metal+'ret1']].dropna()
 x['mode']=np.select([(x.iloc[:,0]<0)&(x.iloc[:,1]>0),(x.iloc[:,0]>0)&(x.iloc[:,1]<0),
                     (x.iloc[:,0]>0)&(x.iloc[:,1]>0)],['longs_down_shorts_up','longs_up_shorts_down','both_up'],default='both_down_or_flat')
 for mode,a in x.groupby('mode'):decomp.append({'metal':metal,'mode':mode,'n':len(a),'mean_same_week_return_pct':float(100*np.expm1(a.iloc[:,2]).mean())})
result={'price_results':price_results,'fund_results':fund_results,'structural_correlations':structural,
 'decomposition':decomp,'clock_audit':clock_audit,'excluded_observation_windows':blackouts,
 'limitations':'10-day clock plus generous blackout exclusion is a conservative availability approximation, not complete historical release timestamps; latest historical data include revisions. Position-date tests are retrospective.'}
json_save('round2_results.json',result)
print('PRICE ALL')
for r in price_results:
 if r['period']=='all':print(r['clock'],r['target'],r['model'],round(r['mse_change_pct'],3),r.get('holm_p'))
print('FUND ALL')
for r in fund_results:
 if r['period']=='all':print(r['target'],r['model'],round(r['mse_change_pct'],3),r.get('holm_p'))
print('DECOMPOSITION',json.dumps(decomp))
