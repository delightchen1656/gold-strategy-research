from utils import *

own=['grv1','grv5','grv22','gret','gret5','log_gvz','log_vix']
cross=own+['srv1','srv5','srv22']
models={'own':own,'cross':cross}
for label,cols in [('own',own),('cross',cross)]:
    for feature in ['q_abs','q_scaled','q_pressure']:models[label+'_'+feature]=cols+[feature]
comparisons=[('own','cross')]+[(base,base+'_'+f) for base in ['own','cross'] for f in ['q_abs','q_scaled','q_pressure']]
predictions=[];results=[]
specs=[('main','GLD_SLV','rv',0),('with_overnight','GLD_SLV','totalrv',0),('gap_one_day','GLD_SLV','rv',1),('other_issuer','IAU_SIVR','rv',0)]
for variant,pair,typ,gap in specs:
    d=read_panel(ROOT/f'hourly_daily_{pair}.csv')
    run=[]
    for horizon in [1,5]:
        target=f'future_{typ}_{horizon}_gap{gap}'
        pp=walk(d,target,f'end_{horizon}_gap{gap}',models,min_obs=126,logvar=True)
        assert len(pp)>0
        run.append(pp)
    p=pd.concat(run,ignore_index=True);p['variant']=variant;predictions.append(p)
    rr=compare(p,comparisons,block=20,qlike=True,periods=[('all','1900','2099'),('2025','2025','2025-12-31'),('2026','2026','2026-12-31')])
    for r in rr:r['variant']=variant
    results.extend(rr)
    print('Finished risk variant',variant, 'rows',len(p),flush=True)
main=[r for r in results if r['variant']=='main' and r['period']=='all' and r['metric']=='MSE' and r['model']!='cross']
holm(main)
pd.concat(predictions,ignore_index=True).to_csv(ROOT/'hourly_risk_predictions.csv',index=False)
save('hourly_risk_results.json',results)

# Next interval prediction. Estimation uses complete prior days, never earlier bars of the target day.
lead_preds=[];lead_results=[];descriptions={};event_stats=[]
for pair in ['GLD_SLV','IAU_SIVR']:
    a=pd.read_csv(ROOT/f'hourly_{pair}.csv',parse_dates=['date'])
    a['timestamp']=pd.to_datetime(a.timestamp,utc=True)
    for metal in ['g','s']:
        for k in [1,2]:a[f'{metal}sq{k}']=a[f'{metal}lag{k}']**2
    for slot in [750,810,870,930]:a['slot'+str(slot)]=(a.slot==slot).astype(float)
    slots=['slot'+str(k) for k in [750,810,870,930]]
    desc=[]
    for lag in [-2,-1,0,1,2]:
        other=a.groupby('date').sr.shift(-lag)
        z=pd.concat([a.gr,other],axis=1).dropna()
        desc.append({'gold_leads_silver_slots':lag,'n':len(z),'corr':float(z.iloc[:,0].corr(z.iloc[:,1]))})
    # Pure timestamp artifact: mark silver one interval late, preserving its actual prices.
    a['fake_silver_delayed']=a.groupby('date').sr.shift(1)
    faked=a.groupby('date').fake_silver_delayed.shift(-1)
    descriptions[pair]={'lag_correlations':desc,'fabricated_one_slot_lead_corr':float(a.gr.corr(faked)),
                        'caveat':'Fake shifted clock is a diagnostic only; not a real economic lead.'}
    for metal,other in [('g','s'),('s','g')]:
        for kind in ['return','variance']:
            suffix='lag' if kind=='return' else 'sq'
            base=[f'{metal}{suffix}1',f'{metal}{suffix}2']+slots
            plus=base+[f'{other}{suffix}1',f'{other}{suffix}2']
            z=a.dropna(subset=plus+[metal+'r']).copy()
            z['target_value']=z[metal+'r'] if kind=='return' else z[metal+'r']**2
            run=[]
            for day,testing in z.groupby('date'):
                train=z[z.date<day]
                if train.date.nunique()<126:continue
                y=train.target_value.to_numpy()
                for name,cols in [('own',base),('cross',plus)]:
                    raw=train[cols].to_numpy();mu=raw.mean(0);sd=raw.std(0);sd[sd<1e-12]=1
                    x=np.column_stack([np.ones(len(train)),(raw-mu)/sd]);b=np.linalg.lstsq(x,y,rcond=None)[0]
                    xx=np.column_stack([np.ones(len(testing)),(testing[cols].to_numpy()-mu)/sd]);forecasts=xx@b
                    if kind=='variance':forecasts=np.maximum(forecasts,1e-12)
                    for (_,row),f in zip(testing.iterrows(),forecasts):
                        run.append({'date':str(day.date()),'timestamp':str(row.timestamp),'slot':int(row.slot),'minutes':int(row.minutes),
                                    'metal':metal,'kind':kind,'model':name,'actual':float(row.target_value),'forecast':float(f),
                                    'training_days':int(train.date.nunique()),'last_training_day':str(train.date.max().date()),'pair':pair})
            p=pd.DataFrame(run);lead_preds.append(p)
            p['loss']=(p.actual-p.forecast)**2
            for period,start,end in [('all','1900','2099'),('2025','2025','2025-12-31'),('2026','2026','2026-12-31')]:
                b=p[(p.date>=start)&(p.date<=end)]
                daily=b.groupby(['date','model']).loss.mean().unstack()
                if len(daily)==0:continue
                r={'pair':pair,'metal':metal,'kind':kind,'period':period,'first':daily.index[0],'last':daily.index[-1]}
                r.update(loss_test(daily.own,daily.cross,block=20));lead_results.append(r)
            for section,mask in [('morning',p.slot<780),('afternoon',p.slot>=780),('last_half_hour',p.slot==930),('full_hour',p.slot<930)]:
                b=p[mask].groupby(['date','model']).loss.mean().unstack()
                rr={'pair':pair,'metal':metal,'kind':kind,'section':section};rr.update(loss_test(b.own,b.cross,block=20));event_stats.append(rr)
            # Leave the largest five baseline daily errors out; this is an explicit diagnostic.
            daily=p.groupby(['date','model']).loss.mean().unstack()
            reduced=daily.drop(daily.own.nlargest(5).index)
            r={'pair':pair,'metal':metal,'kind':kind,'section':'exclude_top5_error_days'}
            r.update(loss_test(reduced.own,reduced.cross,block=20));event_stats.append(r)
            print('Finished interval',pair,metal,kind,'days',len(daily),flush=True)
    # Time-of-day past-only normalization for synchronous tail events.
    for metal in ['g','s']:
        scale=a.groupby('slot')[metal+'r'].transform(lambda x:np.sqrt(x.pow(2).rolling(63).mean().shift(1)))
        a[metal+'_z']=a[metal+'r']/scale
    a['g_big']=a.g_z.abs()>2;a['s_big']=a.s_z.abs()>2
    z=a.dropna(subset=['g_z','s_z'])
    shifted=a.groupby('date').s_big.shift(-1).reindex(z.index)
    descriptions[pair]['tail_events']={'valid_bars':len(z),'gold_large_bars':int(z.g_big.sum()),'silver_large_bars':int(z.s_big.sum()),
                    'same_slot_both':int((z.g_big&z.s_big).sum()),'gold_now_silver_next':int((z.g_big&shifted.fillna(False)).sum())}
    # COT regular Friday 15:30 ET is inside the last half-hour; this is only a calendar association.
    complete=a.groupby('date').filter(lambda x:len(x)==7).copy()
    complete['weekday']=complete.date.dt.dayofweek
    complete=complete[~complete.date.between('2025-10-01','2025-12-31')]
    daily_first=complete[complete.slot<930].groupby('date').gr.apply(lambda x:float(np.sum(x*x)/360))
    last=complete[complete.slot==930].set_index('date').gr.pow(2)/30
    ratio=last/daily_first
    descriptions[pair]['friday_close_risk']={label:{'n':int(mask.sum()),'median_last_vs_previous_per_minute_risk':float(ratio[mask].median())}
        for label,mask in [('friday',ratio.index.dayofweek==4),('other_days',ratio.index.dayofweek!=4)]}

holm([r for r in lead_results if r['period']=='all'])
pd.concat(lead_preds,ignore_index=True).to_csv(ROOT/'hourly_lead_predictions.csv',index=False)
save('hourly_lead_results.json',{'main':lead_results,'sections':event_stats,'descriptions':descriptions})
print('All hourly studies complete.',flush=True)
