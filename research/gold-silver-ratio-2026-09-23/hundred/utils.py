from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent
BASE=ROOT.parent
SEED=20260924

def save(name,obj):
    (ROOT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=str),encoding='utf-8')

def read_panel(path):
    return pd.read_csv(path,parse_dates=['date']).set_index('date')

def blocks(n,B=4000,block=20):
    rng=np.random.default_rng(SEED)
    k=min(block,max(1,n//3))
    return (rng.integers(0,n-k+1,size=(B,int(np.ceil(n/k))))[:,:,None]+np.arange(k)).reshape(B,-1)[:,:n]

def loss_test(base,extra,block=13,B=4000):
    a=np.asarray(base);b=np.asarray(extra);n=len(a)
    r={'n':n,'base_loss':float(a.mean()),'new_loss':float(b.mean()),'change_pct':float(100*(b.mean()/a.mean()-1))}
    if n<40:return dict(r,small_sample=True)
    ix=blocks(n,B,block)
    bp=100*(b[ix].mean(1)/a[ix].mean(1)-1)
    difference=a-b
    centered=difference-difference.mean()
    r.update(ci95=list(np.quantile(bp,[.025,.975])),p_improve=float((1+(centered[ix].mean(1)>=difference.mean()).sum())/(B+1)))
    return r

def holm(rows,pkey='p_improve',outkey='holm_p'):
    ordered=sorted([r for r in rows if pkey in r],key=lambda r:r[pkey])
    cur=0
    for i,r in enumerate(ordered):
        cur=max(cur,(len(ordered)-i)*r[pkey]);r[outkey]=min(1.,cur);r[outkey+'_family_n']=len(ordered)

def walk(frame,target,end_col,models,min_obs=240,start='2012',ridge_models=None,logvar=False,prob=False):
    cols=list(dict.fromkeys(c for cs in models.values() for c in cs))
    z=frame[cols+[target,end_col]].dropna().copy()
    z[end_col]=pd.to_datetime(z[end_col])
    allx=z[cols].to_numpy(float);all_y=z[target].to_numpy(float)
    ends=z[end_col].to_numpy();dates=z.index.to_numpy()
    choices={name:[cols.index(c) for c in cs] for name,cs in models.items()}
    outputs=[]
    for i,dt in enumerate(z.index):
        if dt<pd.Timestamp(start):continue
        train=(dates<dates[i])&(ends<=dates[i])
        if train.sum()<min_obs:continue
        y=all_y[train]
        for name,which in choices.items():
            raw=allx[train][:,which];mu=raw.mean(0);sd=raw.std(0);sd[sd<1e-12]=1.
            x=np.column_stack([np.ones(len(y)),(raw-mu)/sd]);test=np.r_[1.,(allx[i,which]-mu)/sd]
            if ridge_models and name in ridge_models:
                penalty=np.eye(x.shape[1])*ridge_models[name];penalty[0,0]=0
                coef=np.linalg.solve(x.T@x+penalty,x.T@y)
            else:coef=np.linalg.lstsq(x,y,rcond=None)[0]
            forecast=float(test@coef)
            if prob:forecast=float(np.clip(forecast,1e-6,1-1e-6))
            row={'date':str(dt.date()),'target':target,'model':name,'actual':float(all_y[i]),'forecast':forecast,
                 'training_n':int(train.sum()),'latest_label':str(pd.Timestamp(ends[train].max()).date()),'label_end':str(z[end_col].iloc[i].date())}
            if logvar:
                smear=float(np.exp(y-x@coef).mean())
                row.update(variance_forecast=float(np.exp(forecast)*smear),smear=smear)
            outputs.append(row)
    return pd.DataFrame(outputs)

def compare(pred,comparisons,block=13,periods=None,qlike=False):
    if periods is None:periods=[('all','1900','2099')]
    rows=[]
    for target,a in pred.groupby('target'):
        for label,start,end in periods:
            b=a[(a.date>=start)&(a.date<=end)]
            if b.empty:continue
            w=b.pivot(index='date',columns='model',values='forecast');y=b.groupby('date').actual.first()
            for base,extra in comparisons:
                ix=w[[base,extra]].dropna().index
                if len(ix)==0:continue
                r={'target':target,'period':label,'baseline':base,'model':extra,'first':ix[0],'last':ix[-1],'metric':'MSE'}
                r.update(loss_test((w.loc[ix,base]-y.loc[ix])**2,(w.loc[ix,extra]-y.loc[ix])**2,block=block));rows.append(r)
                if qlike:
                    v=b.pivot(index='date',columns='model',values='variance_forecast')
                    truth=np.exp(y.loc[ix])
                    loss=lambda c:truth/v.loc[ix,c]-np.log(truth/v.loc[ix,c])-1
                    rr={k:r[k] for k in ['target','period','baseline','model','first','last']};rr['metric']='QLIKE'
                    rr.update(loss_test(loss(base),loss(extra),block=block));rows.append(rr)
    return rows

def fit_coeff(frame,yname,cols,block=13,B=4000):
    d=frame[cols+[yname]].dropna();raw=d[cols].to_numpy(float);y=d[yname].to_numpy(float)
    mu=raw.mean(0);sd=raw.std(0);sd[sd<1e-12]=1.
    x=np.column_stack([np.ones(len(d)),(raw-mu)/sd]);b=np.linalg.lstsq(x,y,rcond=None)[0]
    ix=blocks(len(d),B,block);out=np.empty((B,len(b)))
    for i in range(B):out[i]=np.linalg.lstsq(x[ix[i]],y[ix[i]],rcond=None)[0]
    lo,hi=np.quantile(out,[.025,.975],axis=0)
    vifs=[]
    for k in range(1,x.shape[1]):
        other=np.delete(x,k,axis=1);res=x[:,k]-other@np.linalg.lstsq(other,x[:,k],rcond=None)[0]
        vifs.append(float(1/np.mean(res**2)) if np.mean(res**2)>1e-14 else None)
    stats=[]
    for k,name in enumerate(['intercept']+cols):
        tails=min(1.,2*min((1+(out[:,k]<=0).sum())/(B+1),(1+(out[:,k]>=0).sum())/(B+1)))
        stats.append({'factor':name,'beta_std_x':float(b[k]),'ci95':[float(lo[k]),float(hi[k])],
                      'bootstrap_sign_p_approx':float(tails),'x_mean':None if k==0 else float(mu[k-1]),'x_sd':None if k==0 else float(sd[k-1]),
                      'vif':None if k==0 else vifs[k-1]})
    mse=np.mean((y-x@b)**2);var=np.mean((y-y.mean())**2)
    return {'target':yname,'n':len(d),'first':str(d.index[0]),'last':str(d.index[-1]),'r2_in_sample':float(1-mse/var),
            'condition_number_standardized':float(np.linalg.cond(x)),'block':block,'bootstrap_B':B,'coefficients':stats,
            'note':'Predictors standardized using fixed full-fit sample SD; conditional association, not causal. Percentile moving-block intervals.'}

def corr_ci(x,y,block=13,B=4000):
    a=pd.DataFrame({'x':x,'y':y}).dropna();u=a.x.to_numpy();v=a.y.to_numpy();ix=blocks(len(a),B,block)
    du=u[ix]-u[ix].mean(1)[:,None];dv=v[ix]-v[ix].mean(1)[:,None]
    rho=(du*dv).sum(1)/np.sqrt((du**2).sum(1)*(dv**2).sum(1))
    return {'n':len(a),'corr':float(np.corrcoef(u,v)[0,1]),'ci95':list(np.quantile(rho,[.025,.975]))}
