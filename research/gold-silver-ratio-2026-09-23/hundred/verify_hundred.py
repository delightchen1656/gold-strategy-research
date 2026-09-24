"""Separate reconstruction of targets, estimation clocks and selected stored forecasts."""
from utils import ROOT,BASE,read_panel,save
import pandas as pd
import numpy as np
import json,hashlib
checks=[];counts={}
def check(name,ok,detail=None):
 checks.append({'check':name,'passed':bool(ok),'detail':detail})
 if not ok:raise AssertionError(name+': '+str(detail))
d=read_panel(ROOT/'daily_panel.csv');g=np.log(d.gold.to_numpy());s=np.log(d.silver.to_numpy());rg=np.diff(g,prepend=np.nan)
count=0;maxerr=0.
for h in [5,20]:
 for i in range(len(d)-h-1):
  gold=g[i+h+1]-g[i+1];ratio=gold-(s[i+h+1]-s[i+1])
  logvar=np.log(252*np.mean(rg[i+2:i+h+2]**2))
  for key,val in [(f'future_return{h}',gold),(f'future_ratio{h}',ratio),(f'future_logvar{h}',logvar)]:
   err=abs(d[key].iloc[i]-val);maxerr=max(maxerr,err);checkval=np.isclose(d[key].iloc[i],val,atol=1e-10)
   if not checkval:raise AssertionError((i,key,val,d[key].iloc[i]))
   count+=1
check('Daily targets rebuilt with one unused complete trading day',True,{'values':count,'max_abs_error':maxerr});counts['daily_target_values']=count
hourcount=0
for pair in ['GLD_SLV','IAU_SIVR']:
 z=read_panel(ROOT/f'hourly_daily_{pair}.csv');bars=pd.read_csv(ROOT/f'hourly_{pair}.csv',parse_dates=['date'])
 for date,a in bars.groupby('date'):
  check('Bar sequence '+pair+' '+str(date.date()),a.slot.tolist()==[570,630,690,750,810,870,930])
  for metal in ['g','s']:
   prices=a[metal+'_close'].to_numpy();ret=np.diff(np.log(prices),prepend=np.log(a[metal+'_open'].iloc[0]))
   check('Intraday return identity '+pair+metal+str(date.date()),np.allclose(ret,a[metal+'r'],atol=1e-12))
   check('Intraday variation '+pair+metal+str(date.date()),np.isclose(np.dot(ret,ret),z.loc[date,metal+'rv'],atol=1e-12))
   hourcount+=len(a)+1
 for typ in ['rv','totalrv']:
  for gap in [0,1]:
   for h in [1,5]:
    for i in range(len(z)-h-gap):
     a=z['g'+typ].iloc[i+gap+1:i+gap+h+1].to_numpy();got=z[f'future_{typ}_{h}_gap{gap}'].iloc[i]
     if not np.isfinite(a).all():check('Missing target preserved',pd.isna(got));continue
     check('Hourly future target',np.isclose(got,np.log(np.mean(a)),atol=1e-10));hourcount+=1
 check('Crash dates are not silently treated as complete',not z.loc['2026-01-30','full_day'] and not z.loc['2026-02-02','full_day'])
counts['hourly_target_or_component_values']=hourcount
OWN=['gvol5','gvol20','gvol60','gret5','gret20'];MAC=['log_vix','dollar20','real20','sp20','log_gvz'];B=OWN+MAC
daily={'base':B,'speed':B+['qret5'],'accel':B+['qret5','qaccel'],'raw':B+['speed5_abs'],'standard':B+['qabs'],
 'residual':B+['surprise_abs'],'signed':B+['qpos_shock','qneg_shock'],'curve':B+['qabs','qabs_squared'],
 'silver':B+['svol5','svol20'],'silver_ratio':B+['svol5','svol20','qabs'],
 'down_control':B+['gold_down'],'down_ratio':B+['gold_down','qpos_shock','qabs_gold_down'],
 'state_base':B+['gvz_high'],'state_ratio':B+['gvz_high','qabs','qabs_high_gvz'],'event':B+['extreme_first','extreme_continues']}
R=['qret5','qabs','svol20'];F=['g_mm_net','s_mm_net','g_mm_net_delta','s_mm_net_delta'];E=['copper20','oil20','breakeven20'];FULL=B+R+F
factor={'own':OWN,'macro':B,'ratio':B+R,'fund':B+F,'full':FULL,'extended':FULL+E,'ridge10':FULL,'nonlinear':FULL+['qabs_squared','qabs_high_gvz']}
FB=B+['qret5'];fund={'base':FB,'managed':FB+F,'producer':FB+['g_producer_net_delta','s_producer_net_delta'],'swap':FB+['g_swap_net_delta','s_swap_net_delta'],
 'other':FB+['g_other_net_delta','s_other_net_delta'],'spread':FB+['g_spread','s_spread'],'crowding':FB+['relative_crowding'],
 'tails':FB+['g_tail','s_tail'],'unwind':FB+['g_both_contract','s_both_contract','g_oi_delta','s_oi_delta']}
H=['grv1','grv5','grv22','gret','gret5','log_gvz','log_vix'];HC=H+['srv1','srv5','srv22'];hour={'own':H,'cross':HC}
for name,cols in [('own',H),('cross',HC)]:
 for feature in ['q_abs','q_scaled','q_pressure']:hour[name+'_'+feature]=cols+[feature]
refits=0;maxrefit=0.;clockrows=0
def verify_predictions(filename,frame,models,endfunc,subset=None):
 global refits,maxrefit,clockrows
 p=pd.read_csv(ROOT/filename)
 if subset:p=p.query(subset)
 check('Finite forecasts '+filename,np.isfinite(p.forecast).all())
 check('No future training outcomes '+filename,(pd.to_datetime(p.latest_label)<=pd.to_datetime(p.date)).all())
 check('Forecast labels after signals '+filename,(pd.to_datetime(p.label_end)>pd.to_datetime(p.date)).all());clockrows+=len(p)
 allcols=list(dict.fromkeys(x for cols in models.values() for x in cols))
 for (target,model),a in p.groupby(['target','model']):
  end=endfunc(target);z=frame.dropna(subset=allcols+[target,end]).copy();z[end]=pd.to_datetime(z[end])
  for j in [0,len(a)//2,len(a)-1]:
   row=a.iloc[j];dt=pd.Timestamp(row.date);train=z[(z.index<dt)&(z[end]<=dt)]
   raw=train[models[model]].to_numpy();mu=raw.mean(0);sd=raw.std(0);sd[sd<1e-12]=1
   x=np.column_stack([np.ones(len(train)),(raw-mu)/sd]);y=train[target].to_numpy();t=np.r_[1,(z.loc[dt,models[model]].to_numpy(float)-mu)/sd]
   if model=='ridge10':
    aug=np.diag(np.r_[0,np.full(len(models[model]),np.sqrt(10))]);coef=np.linalg.lstsq(np.vstack([x,aug]),np.r_[y,np.zeros(len(models[model])+1)],rcond=None)[0]
   else:coef=np.linalg.lstsq(x,y,rcond=None)[0]
   value=t@coef
   if target.startswith('tail'):value=np.clip(value,1e-6,1-1e-6)
   error=abs(value-row.forecast);maxrefit=max(maxrefit,error);refits+=1
   check('Independent forecast '+filename+target+model+row.date,error<1e-8)
   check('Training count '+filename,len(train)==row.training_n)
   if 'variance_forecast' in row and pd.notna(row.variance_forecast):
    smear=np.exp(y-x@coef).mean();check('Variance retransformation '+filename,np.isclose(np.exp(value)*smear,row.variance_forecast,rtol=1e-9))
w=read_panel(ROOT/'weekly_panel.csv')
for filename,models in [('daily_predictions.csv',daily),('factor_predictions.csv',factor),('fund_predictions.csv',fund)]:
 verify_predictions(filename,w,models,lambda t:'end5' if t.endswith('5') else 'end20')
for variant,pair in [('main','GLD_SLV'),('with_overnight','GLD_SLV'),('gap_one_day','GLD_SLV'),('other_issuer','IAU_SIVR')]:
 verify_predictions('hourly_risk_predictions.csv',read_panel(ROOT/f'hourly_daily_{pair}.csv'),hour,lambda t:'end_'+t.split('_')[-2]+'_'+t.split('_')[-1],subset=f"variant == '{variant}'")
m=read_panel(ROOT/'monthly_panel.csv')
for kind,cols in [('gold',['g1','g12']),('silver',['s1','s12']),('ratio',['q1','q12'])]:
 verify_predictions('monthly_predictions.csv',m,{'base':cols,'level':cols+['z'],'asymmetric':cols+['zpos','zneg']},lambda t:'end',subset=f"target == '{kind}_12'")
counts.update(independent_forecast_refits=refits,max_abs_refit_error=maxrefit,forecast_clock_rows=clockrows)
# Every newly reported full-period MSE is reassembled from stored errors, without the analysis comparison helper.
testrows=json.loads((ROOT/'inference_audit.json').read_text())['tests'];msechecks=0
cache={}
for r in testrows:
 source=r['source'];file={'measurement_results.json':'monthly_predictions.csv','hourly_lead_results.json':'hourly_lead_predictions.csv'}.get(source,source.replace('_results.json','_predictions.csv'))
 if file not in cache:cache[file]=pd.read_csv(ROOT/file)
 p=cache[file]
 if source=='hourly_lead_results.json':
  p=p[(p.pair==r['pair'])&(p.metal==r['metal'])&(p.kind==r['kind'])].copy();p['loss']=(p.forecast-p.actual)**2
  a=p.groupby(['date','model']).loss.mean().unstack();base,new=a.own.mean(),a.cross.mean()
 else:
  p=p[p.target==r['target']]
  if 'variant' in r:p=p[p.variant==r['variant']]
  vals={}
  for model in [r['baseline'],r['model']]:
   a=p[p.model==model];vals[model]=np.mean((a.forecast-a.actual)**2)
  base,new=vals[r['baseline']],vals[r['model']]
 check('Independent MSE '+source,np.isclose(100*(new/base-1),r['change_pct'],atol=1e-8));msechecks+=1
counts['independent_mse_comparisons']=msechecks
# Coefficients reproduced using a raw-unit design rather than the analysis standardized design.
co=json.loads((ROOT/'factor_coefficients.json').read_text());coef_checks=0
for target,rec in co.items():
 true_target=rec['target'];cols=[a['factor'] for a in rec['coefficients'][1:]]
 sample=w.dropna(subset=FULL+E+['qabs_high_gvz',true_target]);x=np.column_stack([np.ones(len(sample)),sample[cols]]);b=np.linalg.lstsq(x,sample[true_target],rcond=None)[0]
 expected=np.r_[b[0]+sample[cols].mean().to_numpy()@b[1:],b[1:]*sample[cols].std(ddof=0).to_numpy()]
 check('Full fit coefficients '+target,np.allclose(expected,[r['beta_std_x'] for r in rec['coefficients']],atol=1e-8));coef_checks+=len(expected)
counts['independent_coefficients']=coef_checks
lead=pd.read_csv(ROOT/'hourly_lead_predictions.csv');check('Intraday training uses earlier full days',(pd.to_datetime(lead.last_training_day)<pd.to_datetime(lead.date)).all());counts['hourly_lead_clock_rows']=len(lead)
# Archive hashes identify exact empirical artifacts, not a guarantee about historical provider revisions.
hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in ROOT.glob('*.csv')}
save('verification.json',{'passed':True,'counts':counts,'checks_total':len(checks),'failed':[x for x in checks if not x['passed']],
 'hashes':hashes,'limitations':['No complete historical COT release timestamps or first-release vintages.','Hourly data miss an extreme crash session and do not cover global 24-hour futures.','Expanding-window retrospective testing is not a prospective blind trial.','Bootstrap uncertainty assumes useful local dependence blocks and is approximate under structural breaks.']})
print(json.dumps(counts,indent=2));print('Verification passed',len(checks),'checks')
