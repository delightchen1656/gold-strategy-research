from utils import *
import math
families=[]
for filename in ['daily_results.json','factor_results.json','fund_results.json','hourly_risk_results.json']:
 for r in json.loads((ROOT/filename).read_text()):
  if r['period']=='all' and r['metric']=='MSE':families.append(dict(r,source=filename))
for r in json.loads((ROOT/'measurement_results.json').read_text())['monthly_predictive_results']:
 if r['period']=='all':families.append(dict(r,source='measurement_results.json'))
for r in json.loads((ROOT/'hourly_lead_results.json').read_text())['main']:
 if r['period']=='all':families.append(dict(r,source='hourly_lead_results.json',metric='MSE'))
holm(families,outkey='global_holm_p')
coef=[]
for target,rec in json.loads((ROOT/'factor_coefficients.json').read_text()).items():
 if target.endswith('_extended'):continue
 for r in rec['coefficients'][1:]:coef.append(dict(r,target=target))
holm(coef,pkey='bootstrap_sign_p_approx',outkey='coefficient_holm_p')
out={'primary_forecast_comparisons':len(families),'raw_p_below_05':sum(r.get('p_improve',1)<.05 for r in families),
 'global_holm_below_05':sum(r.get('global_holm_p',1)<.05 for r in families),'tests':families,
 'primary_full_coefficients':coef,'note':'Primary forecast family includes all full-period MSE comparisons, including alternate intraday variants; yearly/section and QLIKE checks are diagnostics, not independent confirmatory discoveries. This family was assembled exhaustively, not selected for significance. Coefficient sign-bootstrap p values are approximate; intervals are marginal, not simultaneous.'}
p=pd.read_csv(ROOT/'hourly_lead_predictions.csv');p['loss']=(p.actual-p.forecast)**2
precision=[];duration=[]
for (pair,metal,kind),a in p.groupby(['pair','metal','kind']):
 wide=a.pivot(index=['date','timestamp'],columns='model',values='loss');diff=wide.own-wide.cross
 daily=wide.groupby(level=0).mean();delta=daily.own-daily.cross
 se_bar=diff.std(ddof=1)/np.sqrt(len(diff));se_day=delta.std(ddof=1)/np.sqrt(len(delta))
 r={'pair':pair,'metal':metal,'kind':kind,'bar_n':len(diff),'day_n':len(delta),'mean_loss_improvement':float(diff.mean()),
    'naive_bar_se':float(se_bar),'independent_day_se':float(se_day),'naive_normal_two_sided_p':math.erfc(abs(diff.mean()/se_bar)/np.sqrt(2)),
    'block_checks':{str(k):loss_test(daily.own,daily.cross,block=k) for k in [1,10,20,40]}}
 precision.append(r)
 if kind=='variance':
  a=a.copy();a['per_minute_loss']=a.loss/a.minutes.pow(2)
  day=a.groupby(['date','model']).per_minute_loss.mean().unstack()
  r={'pair':pair,'metal':metal,'definition':'Same forecasts transformed to variance per minute; actual/predicted bar variance divided by observed bar length; score daily average.'}
  r.update(loss_test(day.own,day.cross,block=20));duration.append(r)
out['precision_audit']=precision;out['duration_score_audit']=duration
save('inference_audit.json',out)
print('Full-period tests',len(families),'raw',out['raw_p_below_05'],'global significant',out['global_holm_below_05'])
print('Lowest global p',sorted((r['global_holm_p'],r['source'],r['target'] if 'target' in r else r['kind'],r.get('model')) for r in families)[:8])
