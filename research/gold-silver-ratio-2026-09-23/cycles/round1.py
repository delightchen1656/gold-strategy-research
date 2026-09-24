from common import *

d=make_panel()
w=weekly(d)
models=risk_models();runs=[]
for target,h in [('future_vol5',5),('future_vol20',20),('future_return20',20)]:
 runs.append(predict(w,target,'end'+str(h),models))
p=pd.concat(runs,ignore_index=True);p.to_csv(ROOT/'round1_predictions.csv',index=False)
comparisons=[('macro','gvz')]+[('gvz',name) for name in FEATURES]
results=compare(p,comparisons)
holm_adjust(results,lambda r:r['period']=='all' and r['baseline']=='gvz' and r['target'].startswith('future_vol'))
w.to_csv(ROOT/'round1_weekly_panel.csv');d.to_csv(ROOT/'daily_primary_panel.csv')
states=[]
s=w.dropna(subset=['qz','log_gvz','sp_change5','vix_change5','gvz_change5']).copy()
s['state']=np.select([s.qz>1.5,s.qz<-1.5],['ratio_up_fast','ratio_down_fast'],default='ordinary')
for name,a in s.groupby('state'):
 states.append({'state':name,'n':len(a),'mean_gold_5d_pct':100*np.expm1(a.gret5).mean(),
 'mean_silver_5d_pct':100*np.expm1(a.sret5).mean(),'median_sp_5d_pct':100*np.expm1(a.sp_change5).median(),
 'median_vix_5d_pct':100*np.expm1(a.vix_change5).median(),'median_gvz_5d_pct':100*np.expm1(a.gvz_change5).median(),
 'fraction_gold_positive':float((a.gret5>0).mean())})
audit={'price_start':d.index[0],'price_end':d.index[-1],'daily_n':len(d),'gvz_first_aligned':d.log_gvz.first_valid_index(),
       'prediction_rows':len(p),'state_first':s.index[0],'state_last':s.index[-1],
       'all_models_same_dates':all(x.groupby('model').size().nunique()==1 for _,x in p.groupby('target'))}
json_save('round1_results.json',{'audit':audit,'results':results,'states':states,
 'method':'4000 moving-block resamples, block length 13 weekly observations. Holm family = 5 features x 2 risk horizons. Latest-vintage pseudoreal-time study, not causal identification.'})
print(json.dumps({'audit':audit,'primary_all':[r for r in results if r['period']=='all'],'states':states},indent=2,default=str))
