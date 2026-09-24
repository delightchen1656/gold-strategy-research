"""Independent alignment and arithmetic checks, without fitting or selecting models."""
from pathlib import Path
import json
import numpy as np
import pandas as pd

root=Path(__file__).resolve().parent
res=json.loads((root/'results.json').read_text(encoding='utf-8'))
px=pd.read_csv(root/'daily_etf_prices.csv',parse_dates=['date']).set_index('date')
wk=pd.read_csv(root/'weekly_risk_panel.csv',parse_dates=['date','label_end']).set_index('date')
glog=np.log(px.GLD.to_numpy())
daily_return=np.diff(glog,prepend=np.nan)
n=0
for dt,row in wk.dropna(subset=['log_future_vol']).iterrows():
 i=px.index.get_loc(dt)
 future=daily_return[i+2:i+22]
 assert len(future)==20
 assert row.label_end==px.index[i+21]
 assert np.isclose(row.log_future_vol,np.log(np.sqrt(np.mean(future**2)*252)),atol=1e-12)
 assert np.isclose(row.future_return,glog[i+21]-glog[i+1],atol=1e-12)
 n+=1
count=0
for fname,table in [('risk_predictions.csv','risk_results'),('cot_predictions.csv','cot_results')]:
 pred=pd.read_csv(root/fname)
 assert (pd.to_datetime(pred.latest_training_label)<=pd.to_datetime(pred.date)).all()
 assert (pd.to_datetime(pred.label_end)>pd.to_datetime(pred.date)).all()
 assert np.isfinite(pred[['forecast','actual']]).all().all()
 for result in res[table]:
  p=pred[pred.target==result['target']]
  if 'training_variant' in result:p=p[p.training_variant==result['training_variant']]
  if result['period']=='2012-2018':p=p[(p.date>='2012')&(p.date<='2018-12-31')]
  if result['period']=='2019-2025':p=p[(p.date>='2019')&(p.date<='2025-12-31')]
  b=p[p.model==result['baseline']].set_index('date')
  x=p[p.model==result['model']].set_index('date')
  assert b.index.equals(x.index) and len(b)==result['n']
  assert np.allclose(b.actual,x.actual)
  errb=np.mean(np.square(b.forecast-b.actual));errx=np.mean(np.square(x.forecast-x.actual))
  assert np.isclose(result['mse_change_percent'],100*(errx/errb-1),atol=1e-8)
  count+=1
panel=pd.read_csv(root/'weekly_cot_panel.csv',parse_dates=['date']).set_index('date')
cp=pd.read_csv(root/'cot_predictions.csv')
for h in [1,4]:
 for metal in ['gold','silver']:
  p=cp[(cp.target==f'future_{metal}_position_{h}w')&(cp.model=='base')&(cp.training_variant=='all_history')]
  for row in p.itertuples():
   i=panel.index.get_loc(pd.Timestamp(row.date))
   assert np.isclose(row.actual,panel.iloc[i+h][metal+'_net']-panel.iloc[i][metal+'_net'],atol=1e-12)
out={'status':'passed','independently_checked_risk_windows':n,'independently_recomputed_mse_comparisons':count,
 'training_label_date_checks':'passed','COT_target_alignment':'passed','all_finite':'passed'}
(root/'verification.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps(out,indent=2))
