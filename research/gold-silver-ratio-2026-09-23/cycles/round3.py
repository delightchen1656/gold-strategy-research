from common import *

models=risk_models();comparisons=[('macro','gvz')]+[('gvz',n) for n in FEATURES]
primary=pd.read_csv(ROOT/'round1_predictions.csv')
robust=[];price_audit=[];all_predictions=[]
primary_px=prices_pair()

# Full replacement of both metal prices. This is source/instrument robustness, not independent economies.
for pair in ['IAU_SIVR','GC_SI']:
 d=make_panel(pair);w=weekly(d)
 run=[]
 for target,h in [('future_vol5',5),('future_vol20',20),('future_return20',20)]:run.append(predict(w,target,'end'+str(h),models))
 pred=pd.concat(run,ignore_index=True);pred['variant']=pair;all_predictions.append(pred)
 rr=compare(pred,comparisons)
 for r in rr:r['variant']=pair
 robust.extend(rr)
 # Match the original GLD/SLV evaluation dates to the alternative sample.
 common_dates=pred[pred.target=='future_vol20'].date.unique()
 pp=primary[primary.date.isin(common_dates)]
 for r in compare(pp,comparisons):r['variant']='GLD_SLV_matched_'+pair;robust.append(r)
 other=d[['gold','silver']];ix=other.index.intersection(primary_px.index)
 original=np.log(primary_px.loc[ix]).diff();alt=np.log(other.loc[ix]).diff()
 q0=original.gold-original.silver;q1=alt.gold-alt.silver
 price_audit.append({'pair':pair,'n':len(d),'first':d.index[0],'last':d.index[-1],
  'common_day_ratio_return_corr':float(q0.corr(q1)),
  'largest_abs_daily_log_gold_return':float(np.log(d.gold).diff().abs().max()),
  'largest_abs_daily_log_silver_return':float(np.log(d.silver).diff().abs().max()),
  'ratio_daily_difference_rms_pct':float(100*np.sqrt(np.mean((q0-q1).dropna()**2)))})
 d.to_csv(ROOT/f'round3_daily_{pair}.csv')

# A fixed five-year estimation window; no window-length search.
d=pd.read_csv(ROOT/'daily_primary_panel.csv',parse_dates=['date','end5','end20']).set_index('date')
w=weekly(d);run=[]
for target,h in [('future_vol5',5),('future_vol20',20),('future_return20',20)]:
 run.append(predict(w,target,'end'+str(h),models,window_years=5))
pred=pd.concat(run,ignore_index=True);pred['variant']='rolling_5_years';all_predictions.append(pred)
for r in compare(pred,comparisons):r['variant']='rolling_5_years';robust.append(r)

# Remove forecast windows that touch the pandemic stress interval, not just signal dates.
pp=primary[~((primary.date<='2020-06-30')&(primary.label_end>='2020-02-15'))]
for r in compare(pp,comparisons):r['variant']='exclude_pandemic_overlap';robust.append(r)

# Out-of-period stress check: earlier daily-price models did not use 2026 outcomes.
extended=make_panel(cutoff='2026-09-22',extended=True)
common=extended.index.intersection(d.index)
assert np.allclose(extended.loc[common,'gold'],d.loc[common,'gold'],atol=1e-8,rtol=1e-7)
assert np.allclose(extended.loc[common,'silver'],d.loc[common,'silver'],atol=1e-8,rtol=1e-7)
exw=weekly(extended);run=[]
for target,h in [('future_vol5',5),('future_vol20',20),('future_return20',20)]:
 run.append(predict(exw,target,'end'+str(h),models,start='2026-01-01'))
pred=pd.concat(run,ignore_index=True);pred['variant']='2026_extension';all_predictions.append(pred)
for r in compare(pred,comparisons,periods=[('2026','2026','2026-12-31')]):r['variant']='2026_extension';robust.append(r)
extended.to_csv(ROOT/'round3_daily_2026_extension.csv')
pd.concat(all_predictions,ignore_index=True).to_csv(ROOT/'round3_predictions.csv',index=False)

# Actual spot-ratio monthly data: rolling reference levels, not an assumed permanent 60/80 equilibrium.
m=pd.read_csv(ROOT.parent/'gold_silver_monthly.csv',parse_dates=['date']).set_index('date').loc['1972':'2025-12-31']
lg,ls=np.log(m.gold),np.log(m.silver);q=lg-ls
m['g1']=lg.diff();m['g12']=lg.diff(12);m['q1']=q.diff();m['q12']=q.diff(12)
m['q_z120']=(q-q.rolling(120).mean().shift(1))/q.rolling(120).std().shift(1)
m['q_high']=(m.q_z120-1).clip(lower=0);m['q_low']=(-m.q_z120-1).clip(lower=0)
monthly_predictions=[]
for h in [1,3,12]:
 m['end']=pd.Series(m.index,index=m.index).shift(-(h+1))
 for kind,series,base in [('gold',lg,['g1','g12']),('ratio',q,['q1','q12'])]:
  target=f'{kind}_return_{h}m';m[target]=series.shift(-(h+1))-series.shift(-1)
  mm={'base':base,'rolling_level':base+['q_z120'],'nonlinear_tails':base+['q_high','q_low']}
  p=predict(m,target,'end',mm,start='2000-01-01',min_years=10,min_obs=120);monthly_predictions.append(p)
monthly=pd.concat(monthly_predictions,ignore_index=True);monthly.to_csv(ROOT/'round3_monthly_predictions.csv',index=False)
mr=[]
for target,p in monthly.groupby('target'):
 for period,start,end in [('all','2000','2025-12-31'),('early','2000','2012-12-31'),('recent','2013','2025-12-31')]:
  part=p[(p.date>=start)&(p.date<=end)];wide=part.pivot(index='date',columns='model',values='forecast');actual=part.groupby('date').actual.first()
  for model in ['rolling_level','nonlinear_tails']:
   z={'target':target,'period':period,'model':model,'n':len(actual),'first':wide.index[0],'last':wide.index[-1]}
   z.update(error_stats((wide['base']-actual)**2,(wide[model]-actual)**2,block=24));mr.append(z)
holm_adjust(mr,lambda r:r['period']=='all')

# Realized return decompositions conditional on relative valuation; descriptive only.
desc=[]
for h in [1,3,12]:
 f=pd.DataFrame({'z':m.q_z120,'gold':lg.shift(-(h+1))-lg.shift(-1),'silver':ls.shift(-(h+1))-ls.shift(-1)}).dropna().loc['2000':]
 for name,mask in [('high',f.z>1),('low',f.z<-1),('middle',f.z.abs()<=1)]:
  a=f[mask]
  desc.append({'state':name,'horizon_months':h,'n':len(a),'mean_gold_return_pct':float(100*np.expm1(a.gold).mean()),
   'mean_silver_return_pct':float(100*np.expm1(a.silver).mean()),'ratio_falls_fraction':float((a.gold<a.silver).mean()),
   'gold_rises_fraction':float((a.gold>0).mean())})
m.to_csv(ROOT/'round3_monthly_panel.csv')
result={'robustness':robust,'monthly_results':mr,'monthly_conditional_description':desc,'price_audit':price_audit,
 'new_period_note':'2026 has fewer than 40 weekly observations; no reliable significance claimed. Formulas fixed before inspection, macro history <=2025 retained from prior snapshot, coefficients update only after labels end. This is not a prospective live trial.',
 'input_only_fix_after_lock':'Macro continuity keeps <=2025 snapshot values instead of retrospectively replacing them with new Yahoo history; no feature or parameter selection.'}
json_save('round3_results.json',result)
print('DAILY RISK 20D')
for r in robust:
 if r['target']=='future_vol20' and r['period'] in ['all','2026']:print(r['variant'],r['model'],r['n'],round(r['mse_change_pct'],3),r.get('ci95_pct'))
print('MONTHLY ALL')
for r in mr:
 if r['period']=='all':print(r['target'],r['model'],round(r['mse_change_pct'],3),r['holm_p'])
print('PRICE AUDIT',json.dumps(price_audit,default=str))
