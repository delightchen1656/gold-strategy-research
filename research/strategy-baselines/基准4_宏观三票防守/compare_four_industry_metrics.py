"""Compare Strategy 1, Strategy 3, Baseline4-DD13 and DD15 on common metrics."""
from pathlib import Path
import json, numpy as np, pandas as pd
ROOT=Path(__file__).resolve().parents[2]; HERE=Path(__file__).resolve().parent
COST=.001; MIN_HOLD=7
def load(p,c): return pd.read_csv(p,parse_dates=['date'],na_values=['.']).set_index('date')[c].astype(float)
def lock_lots(desired):
 lots=[];out=[]
 for i,want in enumerate(desired.fillna(0).clip(0,1)):
  cur=sum(x[1] for x in lots)
  if want>cur+1e-12: lots.append([i,want-cur])
  elif want<cur-1e-12:
   need=cur-want
   for lot in lots:
    if need<=1e-12: break
    if i-lot[0]>=MIN_HOLD:
     sold=min(need,lot[1]);lot[1]-=sold;need-=sold
   lots=[x for x in lots if x[1]>1e-12]
  out.append(sum(x[1] for x in lots))
 return pd.Series(out,index=desired.index)
def run(g,target,start):
 p=g.loc[start:];w=lock_lots(target.reindex(p.index).shift(1).fillna(0));gr=p.pct_change().fillna(0);turn=w.diff().abs().fillna(w.abs());r=w*gr-COST*turn;eq=(1+r).cumprod();return p,gr,w,turn,r,eq
def stats(g,target,start):
 p,gr,w,turn,r,eq=run(g,target,start);dd=eq/eq.cummax()-1;years=(eq.index[-1]-eq.index[0]).days/365.25;cagr=eq.iloc[-1]**(1/years)-1
 vol=r.std()*np.sqrt(252);down=np.sqrt((r.clip(upper=0)**2).mean())*np.sqrt(252);ulcer=np.sqrt(np.mean(np.square(dd)))*100
 runs=[];streak=0
 for x in dd<0: streak=streak+1 if x else 0;runs.append(streak)
 monthly=eq.resample('ME').last().pct_change().dropna();q=np.quantile(r,.05);cvar=r[r<=q].mean()
 corr=r.corr(gr);beta=r.cov(gr)/gr.var()
 return {'return_pct':(eq.iloc[-1]-1)*100,'cagr_pct':cagr*100,'annual_volatility_pct':vol*100,
  'sharpe_0rf':cagr/vol if vol else None,'sortino_0target':cagr/down if down else None,
  'max_drawdown_pct':dd.min()*100,'calmar':cagr/abs(dd.min()),'ulcer_index':ulcer,
  'max_underwater_trading_days':max(runs),'positive_month_pct':(monthly>0).mean()*100,
  'daily_var_95_pct':q*100,'daily_cvar_95_pct':cvar*100,'gold_beta':beta,'gold_correlation':corr,
  'average_weight_pct':w.mean()*100,'days_in_gold_pct':(w>0).mean()*100,'full_weight_days_pct':(w>=.999).mean()*100,
  'turnover':turn.sum(),'last_weight_pct':w.iloc[-1]*100}
def main():
 g=load(ROOT/'data/raw/market/london_gold_fixing.csv','london_gold_usd_oz').dropna();ret=g.pct_change();vol=ret.rolling(20).std()*np.sqrt(252)
 aux=pd.concat({'dxy':load(ROOT/'data/raw/market/yahoo_dollar_index.csv','close'),'real':load(ROOT/'data/raw/macro/fred_us_10y_real_yield.csv','value'),'vix':load(ROOT/'data/raw/macro/fred_vix_close.csv','value')},axis=1).sort_index().ffill().reindex(g.index).ffill()
 dxy60=aux.dxy.pct_change(60);votes=((dxy60<0).astype(int)+(aux.real.diff(60)<0).astype(int)+(aux.vix.pct_change(20)<=.15).astype(int))
 t={}
 t['策略1｜低波趋势控仓']=(.10/vol).clip(.25,.75).where((g>g.rolling(200).mean())&(vol<.22),0)
 t['策略3｜美元弱势控仓']=(.12/vol).clip(.25,1).where((g>g.rolling(150).mean())&(dxy60<0),0)
 for name,two in [('DD13',.55),('DD15',.85)]:
  full=(.15/vol).clip(.25,1);x=pd.Series(0.,index=g.index);trend=g>g.rolling(250).mean();x[trend&(votes>=3)]=full[trend&(votes>=3)];x[trend&(votes==2)]=two*full[trend&(votes==2)];x[trend&(votes==1)]=.30*full[trend&(votes==1)];t[name]=x
 rows=[]
 for name,target in t.items():
  row={'strategy':name}
  for prefix,start in [('full','2020-01-01'),('blind','2025-01-01')]:
   for k,v in stats(g,target,start).items(): row[f'{prefix}_{k}']=v
  rows.append(row)
 df=pd.DataFrame(rows);df.to_csv(HERE/'four_strategy_industry_metrics.csv',index=False)
 report={'period':['2020-01-02',str(g.index[-1].date())],'risk_free_rate_assumption':0,'minimum_holding_trading_days':7,'cost_per_weight_change':.001,'metrics':rows}
 (HERE/'four_strategy_industry_metrics.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 cols=['strategy','full_return_pct','full_cagr_pct','full_annual_volatility_pct','full_sharpe_0rf','full_sortino_0target','full_max_drawdown_pct','full_calmar','full_ulcer_index','full_max_underwater_trading_days','full_average_weight_pct','blind_return_pct','blind_max_drawdown_pct','blind_calmar','full_last_weight_pct']
 print(df[cols].round(3).to_json(orient='records',force_ascii=False,indent=2))
if __name__=='__main__':main()
