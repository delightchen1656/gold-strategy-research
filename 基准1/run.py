"""Self-contained frozen spot backtest; external OHLC is read-only."""
from pathlib import Path
import argparse,json,hashlib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from engine import strategy,simulate,metrics
ROOT=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--start',default='2005-01-01');p.add_argument('--end');p.add_argument('--data-root');p.add_argument('--output',default='output');a=p.parse_args()
cfg=json.loads((ROOT/'config.json').read_text(encoding='utf8'));source=Path(a.data_root or json.loads((ROOT/'data_source.json').read_text(encoding='utf8'))['root']);source=source if source.is_absolute() else (ROOT/source).resolve()
ptr=json.loads((source/'CURRENT.json').read_text(encoding='utf8'));mp=source/ptr['manifest']
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(mp)==ptr['sha256'];meta=json.loads(mp.read_text(encoding='utf8'));pq=mp.parent/'daily.parquet';assert sha(pq)==meta['data_sha256']
d=pd.read_parquet(pq);d['date']=pd.to_datetime(d.date);d=d.set_index('date').sort_index()
asof=pd.Timestamp.now(tz='Asia/Shanghai').tz_localize(None).normalize();d=d[d.index<asof]
assert d.index.is_unique and len(d)>120
assert (d[['open','high','low','close']]>0).all().all()
assert (d.high>=d[['open','close','low']].max(axis=1)).all() and (d.low<=d[['open','close','high']].min(axis=1)).all()
sig=strategy(d,cfg);end=a.end or str(d.index[-1].date());mask=(d.index>=a.start)&(d.index<=end);f=d.loc[mask]
assert len(f)>1,'No usable interval'
eq,w,count=simulate(f,np.array([sig[mask],np.ones(mask.sum())]),.003);m=metrics(f,eq,w)
for v in m:v['excess_return_pp']=v['return_pct']-m[1]['return_pct'];v['excess_cagr_pp']=v['cagr_pct']-m[1]['cagr_pct']
out=Path(a.output);out=out if out.is_absolute() else ROOT/out;out.mkdir(parents=True,exist_ok=True)
# Append a placeholder solely to read the completed last bar's unshifted target.
extra=pd.concat([d,d.iloc[[-1]].set_axis([d.index[-1]+pd.Timedelta(days=1)])]);target=float(strategy(extra,cfg)[-1])
report=dict(strategy=cfg['name'],start=str(f.index[0].date()),end=str(f.index[-1].date()),warmup_bars=int((d.index<f.index[0]).sum()),cost_per_side=.003,results=dict(zip(['strategy','london_hold'],m)),source=str(pq),source_sha256=sha(pq),config_sha256=sha(ROOT/'config.json'),signal_date=str(d.index[-1].date()),target_weight=target,note='Spot simulation, next observed open. History previously viewed; no product execution claim.')
(out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
pd.DataFrame({'date':f.index,'strategy_nav':eq[0],'hold_nav':eq[1],'strategy_weight':w[0]}).to_csv(out/'curves.csv',index=False,encoding='utf-8-sig')
annual=[]
for yr in sorted(set(f.index.year)):
 ix=np.where(f.index.year==yr)[0];lo,hi=ix[0],ix[-1];initial=eq[:,lo-1] if lo else np.ones(2);rel=eq[:,ix]/initial[:,None];v=np.column_stack([np.ones(2),rel]);ret=(rel[:,-1]-1)*100;dd=-(v/np.maximum.accumulate(v,axis=1)-1).min(axis=1)*100
 annual.append(dict(year=int(yr),strategy_return_pct=ret[0],hold_return_pct=ret[1],excess_pp=ret[0]-ret[1],strategy_drawdown_pct=dd[0],hold_drawdown_pct=dd[1],note='Actual interval return; partial years not extrapolated'))
pd.DataFrame(annual).to_csv(out/'annual.csv',index=False,encoding='utf-8-sig')
plt.rcParams['font.sans-serif']=['Microsoft YaHei'];plt.rcParams['axes.unicode_minus']=False
fig,ax=plt.subplots(figsize=(12,6));ax.plot(f.index,eq[0],label=cfg['name']);ax.plot(f.index,eq[1],label='London gold buy & hold',color='gray',ls='--');ax.legend();ax.grid(alpha=.2);ax.set_title(f"{cfg['name']} | {f.index[0]:%Y-%m-%d} - {f.index[-1]:%Y-%m-%d}");ax.set_ylabel('NAV');fig.tight_layout();fig.savefig(out/'comparison.png',dpi=150);plt.close(fig)
print(json.dumps(report,ensure_ascii=False,indent=2))
