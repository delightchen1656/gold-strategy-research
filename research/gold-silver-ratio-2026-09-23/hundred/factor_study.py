from utils import *
w=read_panel(ROOT/'weekly_panel.csv');c=read_panel(ROOT/'cot_panel.csv')
OWN=['gvol5','gvol20','gvol60','gret5','gret20']
MAC=['log_vix','dollar20','real20','sp20','log_gvz']
REL=['qret5','qabs','svol20']
FUN=['g_mm_net','s_mm_net','g_mm_net_delta','s_mm_net_delta']
EXT=['copper20','oil20','breakeven20']
full=OWN+MAC+REL+FUN
# All ablations use exactly the full model's complete-data evaluation sample.
models={'own':OWN,'macro':OWN+MAC,'ratio':OWN+MAC+REL,'fund':OWN+MAC+FUN,'full':full,
 'extended':full+EXT,'ridge10':full,'nonlinear':full+['qabs_squared','qabs_high_gvz']}
outs=[];results=[];coeff={};periods={}
for target in ['future_return20','future_logvar20','future_ratio20']:
 p=walk(w,target,'end20',models,min_obs=240,ridge_models={'ridge10':10},logvar=target=='future_logvar20')
 outs.append(p)
 results+=compare(p,[('own','macro'),('macro','ratio'),('macro','fund'),('ratio','full'),('fund','full'),('full','extended'),('full','ridge10'),('full','nonlinear')],qlike=target=='future_logvar20')
 sample=w.dropna(subset=full+EXT+['qabs_high_gvz',target])
 coeff[target]=fit_coeff(sample,target,full)
 coeff[target+'_extended']=fit_coeff(sample,target,full+EXT)
 for label,lo,hi in [('2009_2018','2009','2018-12-31'),('2019_2025','2019','2025-12-31')]:
  periods[target+'_'+label]=fit_coeff(sample.loc[lo:hi],target,full,B=2000)
 print('factor',target,'rows',len(p),flush=True)
pd.concat(outs,ignore_index=True).to_csv(ROOT/'factor_predictions.csv',index=False)
holm([r for r in results if r['metric']=='MSE']);save('factor_results.json',results)
save('factor_coefficients.json',coeff);save('factor_period_coefficients.json',periods)
# Contemporaneous explanatory regression: never label these forecasting coefficients.
macro=['dollar0','real0','sp0','vix0','gvz0'];extra=['breakeven0','copper0','oil0']
mc={}
for target in ['gret20','sret20','qret20']:
 common=w.dropna(subset=macro+extra+[target])
 mc[target+'_base']=fit_coeff(common,target,macro)
 mc[target+'_extended']=fit_coeff(common,target,macro+extra)
 mc[target+'_asymmetry']=fit_coeff(common,target,['dollar0','real0','sp0','gvz0','vix_up','vix_down']+extra)
 for label,lo,hi in [('pre2017','2000','2016-12-31'),('post2017','2017','2025-12-31')]:
  mc[target+'_'+label]=fit_coeff(common.loc[lo:hi],target,macro+extra,B=2000)
save('macro_coefficients.json',mc)
print('Macro coefficients finished',flush=True)
# Same-as-of weekly prices and net contract changes (NOT the delayed tradeable frame).
fundcoef={}
for metal in ['g','s']:
 controls=['dollar20','real20','log_vix','log_gvz']
 fundcoef[metal+'_net_contemporaneous']=fit_coeff(c,metal+'ret1',controls+[metal+'_mm_net_delta'])
 fundcoef[metal+'_long_short_contemporaneous']=fit_coeff(c,metal+'ret1',controls+[metal+'_long_delta',metal+'_short_delta'])
 for side in ['long','short']:
  target=f'future_{metal}_{side}_1w'
  cols=[f'{metal}_{side}_lag{i}' for i in range(4)]+controls+['qret1','qret4']
  fundcoef[f'{metal}_{side}_reverse']=fit_coeff(c,target,cols,B=2000)
save('fund_coefficients.json',fundcoef)
# Heterogeneous positions and risk, all on the conservative public-availability clock.
base=OWN+MAC+['qret5']
fm={'base':base,'managed':base+FUN,'producer':base+['g_producer_net_delta','s_producer_net_delta'],
 'swap':base+['g_swap_net_delta','s_swap_net_delta'],'other':base+['g_other_net_delta','s_other_net_delta'],
 'spread':base+['g_spread','s_spread'],'crowding':base+['relative_crowding'],
 'tails':base+['g_tail','s_tail'],'unwind':base+['g_both_contract','s_both_contract','g_oi_delta','s_oi_delta']}
fo=[];fr=[]
for target in ['future_return20','future_logvar20','future_ratio20','tail_down20','tail_up20']:
 p=walk(w,target,'end20',fm,min_obs=240,logvar=target=='future_logvar20',prob=target.startswith('tail'))
 fo.append(p);fr+=compare(p,[('base',name) for name in fm if name!='base'],qlike=target=='future_logvar20')
 print('fund',target,'rows',len(p),flush=True)
pd.concat(fo,ignore_index=True).to_csv(ROOT/'fund_predictions.csv',index=False)
holm([r for r in fr if r['metric']=='MSE']);save('fund_results.json',fr)
# PCA is a descriptive dimensionality audit, not evidence for a single decision maker.
pca={}
for metal in ['g','s']:
 cols=[metal+'_'+group+'_net_delta' for group in ['mm','producer','swap','other']]
 a=c[cols].dropna();z=(a-a.mean())/a.std(ddof=0);e,v=np.linalg.eigh(z.T@z/len(z));order=np.argsort(e)[::-1]
 pca[metal]={'columns':cols,'variance_shares':(e[order]/e.sum()).tolist(),'first_loadings':v[:,order[0]].tolist(),'n':len(z),
  'unwind_n':int(c[metal+'_both_contract'].sum()),'unwind_oi_change_mean':float(c.loc[c[metal+'_both_contract']==1,metal+'_oi_delta'].mean()),
  'other_oi_change_mean':float(c.loc[c[metal+'_both_contract']==0,metal+'_oi_delta'].mean())}
save('fund_structure.json',pca)
print('Factor and fund studies finished',flush=True)
