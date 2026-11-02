import numpy as np
import pandas as pd

def generate_round5_signal(d,cfg):
    c=d.close;slow=c.rolling(cfg['slow']).mean();fast=c.rolling(cfg['fast']).mean()
    trend=fast>slow*(1+cfg['buffer'])
    breakout=(c>c.rolling(cfg['breakout']).max().shift())&(c>slow)
    entry=(trend|breakout) if cfg['entry_mode']=='either' else ((trend&breakout) if cfg['entry_mode']=='both' else breakout)
    if cfg['reentry_filter']=='ma20':entry&=c>fast
    elif cfg['reentry_filter']=='rising_ma20':entry&=(c>fast)&(fast>fast.shift(5))
    leave=(fast<slow*(1-cfg['exit_buffer'])).to_numpy();entry=entry.to_numpy()
    on=False;peak=0.;blocked=-1;result=[]
    for i,price in enumerate(c):
        if on:
            peak=max(peak,price)
            if leave[i] or price<peak*(1-cfg['stop']):on=False;blocked=i+cfg['cooldown']
        elif i>=blocked and entry[i]:on=True;peak=price
        result.append(float(on))
    return np.r_[0.,result[:-1]]

def simulate(d,signals,cost=.0005):
    n=len(signals);cash=np.ones(n);units=np.zeros(n);last=np.full(n,-1.)
    eq=np.zeros_like(signals,dtype=float);weights=eq.copy();counts=np.zeros(n)
    close=d.close.to_numpy()
    for j,(op,cl) in enumerate(zip(d.open,close)):
        prev=close[j-1] if j else op;known=cash+units*prev;target=signals[:,j]
        trade=(abs(target-last)>1e-8)|(abs(units*prev/known-target)>=.05)
        delta=target*known-units*prev
        spend=np.where(trade&(delta>0),np.minimum(cash,delta),0.);bought=spend/(op*(1+cost))
        sold=np.where(trade&(delta<0),np.minimum(units,-delta/prev),0.)
        sold=np.where(trade&(target==0),units,sold)
        cash+=sold*op*(1-cost)-spend;units+=bought-sold;last=np.where(trade,target,last)
        assert cash.min()>-1e-8 and units.min()>-1e-8
        eq[:,j]=cash+units*cl;weights[:,j]=units*cl/eq[:,j];counts+=(bought+sold)>0
    return eq,weights,counts

def metrics(d,eq,w):
    vals=np.column_stack([np.ones(len(eq)),eq]);years=(d.index[-1]-d.index[0]).days/365.25
    return [dict(return_pct=float((e[-1]-1)*100),cagr_pct=float((e[-1]**(1/years)-1)*100),max_drawdown_pct=float(-(v/np.maximum.accumulate(v)-1).min()*100),average_weight_pct=float(ww.mean()*100)) for e,v,ww in zip(eq,vals,w)]

def generate(d,cfg):
    c=d.close;method=cfg['method']
    if method=='momentum_vote':
        n=cfg['horizon'];votes=sum((c.pct_change(k)>0).astype(int) for k in [n,n*2,n*3])
        enter=(votes>=cfg['votes']).to_numpy();leave=(votes<cfg['votes']).to_numpy()
        ready=c.shift(n*3).notna().to_numpy()
        if cfg['frequency']=='daily':review=np.ones(len(c),bool)
        else:
            keys=d.index.to_period('M' if cfg['frequency']=='monthly' else 'W-FRI')
            review=np.r_[True,keys[1:]!=keys[:-1]]
    elif method=='regression_trend':
        n=cfg['horizon'];y=np.log(c);x=np.arange(n)-(n-1)/2;sxx=(x*x).sum()
        slope=y.rolling(n).apply(lambda z:np.dot(x,z)/sxx,raw=True)
        r2=(slope*slope*sxx/(y.rolling(n).var(ddof=0)*n)).clip(0,1)
        enter=((slope>cfg['slope']/252)&(r2>cfg['r2'])).to_numpy()
        leave=(slope<0).to_numpy();ready=slope.notna().to_numpy();review=np.ones(len(c),bool)
    else:
        avg=c.rolling(cfg['trend']).mean();delta=c.diff();n=cfg['rsi_n']
        gain=delta.clip(lower=0).ewm(alpha=1/n,adjust=False,min_periods=n).mean()
        loss=(-delta.clip(upper=0)).ewm(alpha=1/n,adjust=False,min_periods=n).mean()
        rsi=100-100/(1+gain/loss)
        enter=((c>avg)&(rsi<cfg['buy'])).to_numpy()
        leave=((c<avg*.98)|(rsi>cfg['sell'])).to_numpy();ready=avg.notna().to_numpy();review=np.ones(len(c),bool)
    on=False;peak=0.;blocked=-1;result=[]
    for i,price in enumerate(c):
        if on:
            peak=max(peak,price)
            risk=cfg['stop']>0 and price<peak*(1-cfg['stop'])
            if risk or (review[i] and leave[i]):on=False;blocked=i+5
        elif review[i] and ready[i] and i>=blocked and enter[i]:on=True;peak=price
        result.append(float(on))
    return np.r_[0.,result[:-1]]

def triggers(d,cfg):
    c=d.close;arr=c.to_numpy();n=len(c)
    if cfg['method']=='kama':
        er=(c-c.shift(cfg['n'])).abs()/c.diff().abs().rolling(cfg['n']).sum()
        alpha=(er*(2/(cfg['fast']+1)-2/(cfg['slow']+1))+2/(cfg['slow']+1))**2
        v=np.full(n,np.nan);level=arr[0]
        for t in range(n):
            if np.isfinite(alpha.iloc[t]):level+=float(alpha.iloc[t])*(arr[t]-level);v[t]=level
        up=arr>v*(1+cfg['buffer']);down=arr<v*(1-cfg['buffer'])
        up[:120]=False;down[:120]=False
    elif cfg['method']=='kalman':
        y=np.log(arr);F=np.array([[1.,1.],[0.,1.]])
        R=.0001;Q=np.diag([cfg['q']*R,cfg['q']*R/100]);P=np.eye(2);state=np.array([y[0],0.]);score=np.zeros(n)
        for t,obs in enumerate(y):
            state=F@state;P=F@P@F.T+Q;gain=P[:,0]/(P[0,0]+R)
            state=state+gain*(obs-state[0]);P=P-np.outer(gain,P[0,:]);P=(P+P.T)/2
            score[t]=state[1]/np.sqrt(max(P[1,1],1e-14))
        up=score>cfg['threshold'];down=score<-cfg['threshold'];up[:120]=False;down[:120]=False
    else:
        span=cfg['n'];x=np.linspace(-1,0,span);X=np.column_stack([np.ones(span),x,x*x]);pinv=np.linalg.pinv(X)
        y=np.log(arr);slope=np.full(n,np.nan);r2=np.full(n,np.nan)
        for t in range(span-1,n):
            z=y[t-span+1:t+1];coef=pinv@z;fit=X@coef
            slope[t]=coef[1]/(span-1)*252
            r2[t]=1-np.square(z-fit).sum()/max(np.square(z-z.mean()).sum(),1e-20)
        up=(slope>cfg['threshold'])&(r2>cfg['r2']);down=slope<-cfg['threshold']
    return np.asarray(up),np.asarray(down)

def state(d,up,down,stop,review):
    if review=='weekly':
        periods=d.index.to_period('W-FRI');check=np.r_[True,periods[1:]!=periods[:-1]]
    else:check=np.ones(len(d),bool)
    on=False;peak=0.;blocked=-1;result=[]
    for i,price in enumerate(d.close):
        if on:
            peak=max(peak,price)
            if price<peak*(1-stop) or (check[i] and down[i]):on=False;blocked=i+5
        elif check[i] and i>=blocked and up[i]:on=True;peak=price
        result.append(float(on))
    return np.r_[0.,result[:-1]]

def strategy(d,config):
    if 'components' not in config:return generate_round5_signal(d,config['signal'])
    f=config['components'];base=generate_round5_signal(d,f['base_parameters'])
    linear=generate(d,f['previous_parameters']);q=f['parameters'];up,down=triggers(d,q)
    return np.maximum(np.maximum(base,linear),state(d,up,down,q['stop'],q['review']))
