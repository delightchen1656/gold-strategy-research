from utils import *
d=read_panel(ROOT/'daily_panel.csv');w=read_panel(ROOT/'weekly_panel.csv');c=read_panel(ROOT/'cot_panel.csv')
out={};v=d[['gret1','sret1','qret1']].dropna()
out['identity']={'n':len(v),'return_max_error':float(abs(v.qret1-v.gret1+v.sret1).max()),
 'rank_gold_silver_ratio':int(np.linalg.matrix_rank(v.to_numpy())),
 'examples':[{'gold_logreturn':.01,'silver_logreturn':-.01,'ratio_logreturn':.02},{'gold_logreturn':-.01,'silver_logreturn':-.03,'ratio_logreturn':.02}],
 'equal_point_change':[{'from':40,'to':45,'pct':12.5,'log':float(np.log(45/40))},{'from':100,'to':105,'pct':5,'log':float(np.log(105/100))}]}
x=np.column_stack([np.ones(len(v)),v.gret1]);res=lambda a:a-x@np.linalg.lstsq(x,a,rcond=None)[0]
out['residual_equivalence_max_error']=float(np.max(abs(res(v.qret1.to_numpy())+res(v.sret1.to_numpy()))))
out['variance_decomposition']=[]
for label,a in [('all',v),('2006_2014',v.loc[:'2014']),('2015_2025',v.loc['2015':])]:
 vg=a.gret1.var();vs=a.sret1.var();cov=a.gret1.cov(a.sret1);vq=a.qret1.var()
 out['variance_decomposition'].append({'period':label,'n':len(a),'gold_var':vg,'silver_var':vs,'minus_2cov':-2*cov,'ratio_var':vq,'error':vq-vg-vs+2*cov,'silver_gold_vol_ratio':float(np.sqrt(vs/vg))})
beta=v.gret1.rolling(252).cov(v.sret1)/v.sret1.rolling(252).var()
hedge=v.gret1-beta.shift(1)*v.sret1
out['hedge']={'rolling_beta_quantiles':beta.quantile([.05,.5,.95]).to_dict(),'one_to_one_variance':float(v.loc[hedge.dropna().index,'qret1'].var()),'lagged_min_variance_hedge_variance':float(hedge.var())}
raw=pd.DataFrame(json.loads((BASE/'cycles/sources/cot_full_2025.json').read_text()))
o=pd.to_numeric(raw.open_interest_all)
out['accounting']={'reports':len(raw),'long_balance_max_error':float(abs(pd.to_numeric(raw.tot_rept_positions_long_all)+pd.to_numeric(raw.nonrept_positions_long_all)-o).max()),'short_balance_max_error':float(abs(pd.to_numeric(raw.tot_rept_positions_short)+pd.to_numeric(raw.nonrept_positions_short_all)-o).max())}
out['denominator']={}
for metal in ['g','s']:
 net=c[metal+'_net_contracts'];oi=c[metal+'_oi'];fraction=net/oi
 quantity=net.diff()/oi.shift(1);den=net*(1/oi-1/oi.shift(1));delta=fraction.diff();valid=delta.notna()&quantity.notna()
 out['denominator'][metal]={'n':int(valid.sum()),'opposite_signs':int(((quantity*delta<0)&valid).sum()),'max_decomposition_error':float(abs(delta-quantity-den).max())}
m=read_panel(BASE/'gold_silver_monthly.csv').loc['1972':'2025'].copy()
etf=d[['gold','silver']].resample('MS').mean();etfr=etf.gold/etf.silver
spot=m.ratio.reindex(etf.index);scale=etfr/spot
ratio_daily=(d.gold/d.silver).resample('MS').mean()
out['measurement']={'etf_vs_spot_scale_quantiles':scale.dropna().quantile([0,.5,1]).to_dict(),
 'ratio_of_means_vs_mean_of_ratios_max_pct':float((100*(etfr/ratio_daily-1)).abs().max()),
 'ratio_of_means_vs_mean_of_ratios_median_abs_pct':float((100*(etfr/ratio_daily-1)).abs().median())}
alt=read_panel(BASE/'cycles/round3_daily_GC_SI.csv');qq=np.log(alt.gold/alt.silver).diff();baseq=np.log(d.gold/d.silver).diff()
out['measurement']['futures_etf_daily_corr']=float(qq.corr(baseq))
out['measurement']['futures_etf_weekly_corr']=float(qq.resample('W-FRI').sum(min_count=1).corr(baseq.resample('W-FRI').sum(min_count=1)))
# Intraday targets: each bar is a coarse squared-return component, not tick-level realized variance.
hourly={}
for pair in ['GLD_SLV','IAU_SIVR']:
 z=read_panel(ROOT/f'hourly_daily_{pair}.csv');bars=pd.read_csv(ROOT/f'hourly_{pair}.csv',parse_dates=['date'])
 a=z[z.full_day].copy();record={'complete_days':len(a),'risk':{},'by_slot':[]}
 for metal in ['g','s']:
  rv=a[metal+'rv'];oc=a[metal+'oc']**2;overnight=a[metal+'overnight']**2
  record['risk'][metal]={'sum_oc_squared_over_sum_intraday_rv':float(oc.sum()/rv.sum()),
   'fraction_days_oc_squared_less_than_quarter_rv':float((oc<.25*rv).mean()),
   'overnight_share_sum_variance':float(overnight.sum()/(overnight+rv).sum()),
   'median_overnight_share':float((overnight/(overnight+rv)).median())}
 for slot,aa in bars.groupby('slot'):
  record['by_slot'].append({'slot':int(slot),'minutes':int(aa.minutes.iloc[0]),'n':len(aa),'gold_mean_sq_per_minute':float((aa.gr**2/aa.minutes).mean()),'silver_mean_sq_per_minute':float((aa.sr**2/aa.minutes).mean())})
 calm=a.qoc.abs()<a.qoc.abs().quantile(.25);busy=a.qrv>a.qrv.quantile(.75)
 record['calm_endpoint_busy_path']={'n':int((calm&busy).sum()),'dates':a.index[calm&busy].strftime('%Y-%m-%d').tolist(),'definition':'bottom 25% |open-close log ratio| and top 25% intraday ratio squared variation; descriptive full-sample thresholds'}
 record['excluded_days_daily_returns']=[]
 for date,row in z[~z.full_day].iterrows():record['excluded_days_daily_returns'].append({'date':str(date.date()),'valid_bars':int(row.valid_bars),'gold_return_pct':float(100*np.expm1(row.gret)),'silver_return_pct':float(100*np.expm1(row.sret))})
 hourly[pair]=record
out['hourly_measurement']=hourly
age=(w.index-pd.to_datetime(w.cot_asof)).dt.days
out['timing']={'cot_available_feature_rows':int(w.g_mm_net.notna().sum()),'cot_age_days':age[w.g_mm_net.notna()].value_counts().sort_index().to_dict(),'cot_asof_weekdays':c.index.day_name().value_counts().to_dict(),'macro_lag':'Forecast features use previous available daily observation; explanatory *0 features are contemporaneous.'}
out['decade_ratio']=[];longcoef={}
lg=np.log(m.gold);ls=np.log(m.silver);q=lg-ls
m['lg']=lg;m['ls']=ls;m['lq']=q;m['lag_lq']=q.shift(1);m['qchange']=q.diff()
for label,lo,hi in [('1972_1989','1972','1989'),('1990_2006','1990','2006'),('2007_2016','2007','2016'),('2017_2025','2017','2025')]:
 a=m.loc[lo:hi];out['decade_ratio'].append({'period':label,'n':len(a),'median':float(a.ratio.median()),'q10':float(a.ratio.quantile(.1)),'q90':float(a.ratio.quantile(.9))})
 b=fit_coeff(a,'lg',['ls'],block=24,B=2000);ar=fit_coeff(a,'lq',['lag_lq'],block=24,B=2000)
 for rec in [b,ar]:
  rr=rec['coefficients'][1];rr['raw_beta']=rr['beta_std_x']/rr['x_sd'];rr['raw_ci95']=[x/rr['x_sd'] for x in rr['ci95']]
 phi=ar['coefficients'][1]['raw_beta'];ar['half_life_months']=float(-np.log(2)/np.log(phi)) if 0<phi<1 else None
 ar['warning']='Descriptive AR fit to a potentially nonstationary, structurally changing level; interval is not a unit-root test or guaranteed convergence.'
 longcoef[label]={'price_slope':b,'ratio_ar':ar}
out['long_coefficients']=longcoef
# End-of-month information timestamps and an unused full month precede monthly-average targets.
m.index=m.index+pd.offsets.MonthEnd(0);lg=np.log(m.gold);ls=np.log(m.silver);q=lg-ls
m['g1']=lg.diff();m['g12']=lg.diff(12);m['q1']=q.diff();m['q12']=q.diff(12)
m['s1']=ls.diff();m['s12']=ls.diff(12)
m['z']=(q-q.rolling(120).mean().shift(1))/q.rolling(120).std().shift(1)
m['zpos']=m.z.clip(lower=0);m['zneg']=(-m.z).clip(lower=0)
mp=[];mr=[];adj={}
for kind,series,own in [('gold',lg,['g1','g12']),('silver',ls,['s1','s12']),('ratio',q,['q1','q12'])]:
 m[kind+'_12']=series.shift(-13)-series.shift(-1);m['end']=pd.Series(m.index,index=m.index).shift(-13)
 models={'base':own,'level':own+['z'],'asymmetric':own+['zpos','zneg']}
 p=walk(m,kind+'_12','end',models,min_obs=120,start='2000');mp.append(p)
 mr+=compare(p,[('base','level'),('level','asymmetric')],block=24,periods=[('all','2000','2025'),('before2017','2000','2016-12-31'),('2017plus','2017','2025')])
 adj[kind]=fit_coeff(m.loc['2000':],kind+'_12',own+['zpos','zneg'],block=24)
pd.concat(mp,ignore_index=True).to_csv(ROOT/'monthly_predictions.csv',index=False)
holm([r for r in mr if r['period']=='all']);out['monthly_predictive_results']=mr;out['monthly_adjustment_coefficients']=adj
save('measurement_results.json',out)
m.to_csv(ROOT/'monthly_panel.csv')
print('Measurement and monthly studies complete',flush=True)
