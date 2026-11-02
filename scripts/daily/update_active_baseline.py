"""Active spot-close baseline. Read verified local snapshot; never invent current bars."""
import sys,json,hashlib,subprocess
from pathlib import Path
from datetime import datetime,timezone,timedelta
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.core.baseline_signal import generate_baseline_signal
config=json.loads((ROOT/'config/baseline_1.json').read_text(encoding='utf-8'))
asof=sys.argv[1] if len(sys.argv)>1 else datetime.now(timezone(timedelta(hours=8))).date().isoformat()
out=ROOT/'research/baseline-1'/('active-'+asof);out.mkdir(exist_ok=True)
source=Path(config['data_root'])
if not source.is_absolute():
    source=(ROOT/source).resolve()
current=json.loads((source/'CURRENT.json').read_text(encoding='utf-8'))
manifest=source/current['manifest']
assert hashlib.sha256(manifest.read_bytes()).hexdigest()==current['sha256']
parquet=manifest.parent/'daily.parquet'
try:
    d=pd.read_parquet(parquet)
except ImportError:
    runtime=(ROOT/'../quant/quant_env/Scripts/python.exe').resolve()
    code="import pandas as pd,sys;pd.read_parquet(sys.argv[1])[['date','open','high','low','close','source']].to_json(sys.argv[2],orient='records',force_ascii=False)"
    subprocess.run([str(runtime),'-c',code,str(parquet),str(out/'spot_input.json')],check=True)
    d=pd.read_json(out/'spot_input.json')
d['date']=pd.to_datetime(d.date);d=d.set_index('date').sort_index()
d=d[d.index<pd.Timestamp(asof)]
assert d.index.is_unique and (d.high>=d[['open','close','low']].max(axis=1)).all()
assert (d.low<=d[['open','close','high']].min(axis=1)).all()
cfg=config['signal'];s=d.close
# Dummy next observation only exposes the previous completed bar's signal;
# its invented value is never used for historical prices or valuation.
def target_after(frame):
    extended=pd.concat([frame,frame.iloc[[-1]].set_axis([frame.index[-1]+pd.Timedelta(days=1)])])
    return float(generate_baseline_signal(extended,cfg)[-1])
target=target_after(d)
shifted=generate_baseline_signal(d,cfg)
changes=np.where(np.diff(np.r_[0.,shifted])!=0)[0]
last_exit=None
for i in changes:
    if shifted[i]==0 and i>0:last_exit=str(d.index[i-1].date())
next_ma=(1.02*s.tail(119).sum()-6*s.tail(19).sum())/(6-1.02)
next_breakout=max(s.tail(90).max(),s.tail(119).mean())
def scenario(price,n):
    # Hypothetical consecutive future observations at the same close.
    frame=d.copy()
    for i in range(n):
        day=frame.index[-1]+pd.Timedelta(days=1)
        row=pd.DataFrame({'open':[price],'high':[price],'low':[price],'close':[price]},index=[day])
        frame=pd.concat([frame,row])
        if target_after(frame)>0:return i+1
    return None
scenarios={}
for n in [1,5,10,20]:
    lo=0.;hi=max(next_breakout*2,next_ma*2)
    for _ in range(38):
        mid=(lo+hi)/2
        if scenario(mid,n) is not None:hi=mid
        else:lo=mid
    scenarios[str(n)]=round(hi,2)
report={'strategy':'基准1','version':config['version'],'signal_date':str(d.index[-1].date()),
 'checked_at':datetime.now(timezone(timedelta(hours=8))).isoformat(),'source':str(parquet),
 'source_sha256':hashlib.sha256(parquet.read_bytes()).hexdigest(),'price_basis':config['price_basis'],
 'close':float(s.iloc[-1]),'target_weight':target,'ma20':float(s.tail(20).mean()),'ma120':float(s.tail(120).mean()),
 'last_exit_signal_date':last_exit,'next_bar_ma_entry_threshold':float(next_ma),
 'next_bar_breakout_entry_threshold':float(next_breakout),'constant_future_close_entry_thresholds':scenarios,
 'scenario_note':'Hypothetical equal future closes; observation counts, not calendar days. Strictly exceed thresholds; not forecasts.',
 'products_note':'Fund/bank positions must be recomputed with their calendars and costs; do not reuse old baseline holdings.'}
try:
    from scripts.daily.active_baseline_products import calculate
    report['products']=calculate(ROOT,out,asof,d,cfg)
except Exception as exc:
    report['products_error']=str(exc)
(out/'signal.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
(ROOT/'research/baseline-1/latest_signal.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
