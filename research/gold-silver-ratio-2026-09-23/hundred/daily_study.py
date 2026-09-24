from utils import *
w=read_panel(ROOT/'weekly_panel.csv')
OWN=['gvol5','gvol20','gvol60','gret5','gret20']
STRONG=OWN+['log_vix','dollar20','real20','sp20','log_gvz']
models={'base':STRONG,'speed':STRONG+['qret5'],'accel':STRONG+['qret5','qaccel'],
 'raw':STRONG+['speed5_abs'],'standard':STRONG+['qabs'],
 'residual':STRONG+['surprise_abs'],'signed':STRONG+['qpos_shock','qneg_shock'],
 'curve':STRONG+['qabs','qabs_squared'],'silver':STRONG+['svol5','svol20'],
 'silver_ratio':STRONG+['svol5','svol20','qabs'],
 'down_control':STRONG+['gold_down'],'down_ratio':STRONG+['gold_down','qpos_shock','qabs_gold_down'],
 'state_base':STRONG+['gvz_high'],'state_ratio':STRONG+['gvz_high','qabs','qabs_high_gvz'],
 'event':STRONG+['extreme_first','extreme_continues']}
pairs=[('base','speed'),('speed','accel'),('base','raw'),('base','standard'),('base','residual'),
 ('base','signed'),('standard','curve'),('base','silver'),('silver','silver_ratio'),
 ('down_control','down_ratio'),('state_base','state_ratio'),('base','event')]
outputs=[];results=[]
for target in ['future_logvar5','future_logvar20','future_return20','future_ratio20','tail_down20','tail_up20']:
 h=5 if target.endswith('5') else 20
 p=walk(w,target,f'end{h}',models,min_obs=240,logvar=target.startswith('future_logvar'),prob=target.startswith('tail'))
 outputs.append(p)
 r=compare(p,pairs,block=13,qlike=target.startswith('future_logvar'))
 results+=r
 print('daily',target,'rows',len(p),flush=True)
allp=pd.concat(outputs,ignore_index=True);allp.to_csv(ROOT/'daily_predictions.csv',index=False)
primary=[r for r in results if r['metric']=='MSE'];holm(primary)
save('daily_results.json',results)
# Contributions of each year and extreme observation sensitivity are descriptive, not model selection.
contrib=[]
for target,p in allp.groupby('target'):
 v=p.pivot(index='date',columns='model',values='forecast');y=p.groupby('date').actual.first()
 for extra in ['speed','standard','residual','signed','silver_ratio']:
  base='silver' if extra=='silver_ratio' else 'base'
  a=(v[base]-y)**2;b=(v[extra]-y)**2
  for year in sorted(set(v.index.str[:4])):
   ix=v.index.str.startswith(year)
   contrib.append({'target':target,'model':extra,'period':year,'n':int(ix.sum()),'base_sum_loss':float(a[ix].sum()),'delta_sum_loss':float((b-a)[ix].sum()),'change_pct':float(100*(b[ix].mean()/a[ix].mean()-1))})
  keep=a.nsmallest(len(a)-5).index
  rr={'target':target,'model':extra,'period':'exclude_5_largest_base_loss'};rr.update(loss_test(a.loc[keep],b.loc[keep],block=13));contrib.append(rr)
save('daily_contributions.json',contrib)
# Conditional coefficients are association, with overlapping 20-day targets addressed by weekly blocks.
coef={}
for name,features in [('asymmetry',['qpos_shock','qneg_shock']),('curve',['qabs','qabs_squared']),
 ('state',['gvz_high','qabs','qabs_high_gvz']),('event',['extreme_first','extreme_continues']),
 ('rebound',['gold_down','qpos_shock','qabs_gold_down']),('relative',['qret5','qpos_shock','qneg_shock'])]:
 target='future_ratio20' if name=='relative' else ('future_return20' if name=='rebound' else 'future_logvar20')
 coef[name]=fit_coeff(w,target,STRONG+features)
save('daily_conditional_coefficients.json',coef)
print('Daily studies finished',flush=True)
