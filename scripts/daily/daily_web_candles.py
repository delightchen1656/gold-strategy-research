"""Same-source web OHLC chart; latest row conservatively provisional."""
import sys,json,re
from pathlib import Path
from io import StringIO
from datetime import datetime,timezone,timedelta
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.data.collect_market_data import get

asof=sys.argv[1]
out=ROOT/'research/baseline-1'/('update-'+asof)
out.mkdir(exist_ok=True)
url='https://www.investing.com/currencies/xau-usd-historical-data'
b=get(url)
visible=re.sub(r'\s+',' ',re.sub('<[^>]+>',' ',b.decode('utf-8')))
quote_area=visible.split('Add to Watchlist',1)[-1][:250]
market_closed=bool(re.search(r'\bClosed\b',quote_area))
stamp=datetime.now(timezone(timedelta(hours=8))).isoformat()
(out/'investing_history.raw').write_bytes(b)
def parse_table(raw):
    frame=next(t for t in pd.read_html(StringIO(raw.decode('utf-8'))) if {'Date','Price','Open','High','Low'}.issubset(t.columns)).copy()
    frame.index=pd.to_datetime(frame.Date,format='%b %d, %Y')
    return frame

# Older snapshots extend the same source's default short history window.
# Freshly fetched rows always replace overlapping cached rows.
frames=[]; snapshots=[]
for path in sorted(out.parent.glob('update-*/investing_history.raw')):
    if path.parent.name > 'update-'+asof or path.parent == out:
        continue
    frames.append(parse_table(path.read_bytes())); snapshots.append(str(path))
frames.append(parse_table(b))
t=pd.concat(frames)
t=t[~t.index.duplicated(keep='last')].sort_index()
assert t.index.is_unique
assert (t.High>=t[['Open','Price','Low']].max(axis=1)).all()
assert (t.Low<=t[['Open','Price','High']].min(axis=1)).all()
t=t.loc[t.index<=pd.Timestamp(asof)].tail(30)
assert len(t)>=2
r=t.iloc[-1];p=t.iloc[-2]
report={'source':url,'retrieved_beijing':stamp,'source_timezone':'not established; source session dates preserved',
 'provisional_date':str(t.index[-1].date()),'ohlc':{k:float(r[k]) for k in ['Open','High','Low','Price']},
 'latest_row_change_pct':float((r.Price/p.Price-1)*100),'quote_timestamp':None,
 'previous_session':str(t.index[-2].date()),'previous_ohlc':{k:float(p[k]) for k in ['Open','High','Low','Price']},
 'market_closed':market_closed,'latest_completed':market_closed,
 'window':'30 source trading sessions, including latest provisional session',
 'session_count':len(t),'cached_same_source_snapshots':snapshots,
 'note':'Latest row solid only when page reports Closed; otherwise provisional. Retrieval time is not quote time. No mixed-source candles.'}
(out/'web_candles.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
plt.rcParams['font.sans-serif']=['Microsoft YaHei'];plt.rcParams['axes.unicode_minus']=False
fig,(ax,vax)=plt.subplots(2,1,figsize=(12,8),sharex=True,gridspec_kw={'height_ratios':[4,1]},facecolor='#fafbfd')
ax.set_facecolor('#fafbfd');vax.set_facecolor('#fafbfd')
for i,(d,row) in enumerate(t.iterrows()):
    pending=i==len(t)-1 and not market_closed;color='#d05252' if row.Price>=row.Open else '#16855d'
    ax.vlines(i,row.Low,row.High,color=color,lw=1.5,linestyles='--' if pending else '-')
    ax.add_patch(Rectangle((i-.3,min(row.Open,row.Price)),.6,max(abs(row.Price-row.Open),.15),facecolor='none' if pending else color,edgecolor=color,linestyle='--' if pending else '-',linewidth=1.6))
ax.text(.99,.97,'网页显示已休市：最后一根为完整日线' if market_closed else '最后一根：网页最新OHLC，未确认完成',transform=ax.transAxes,ha='right',va='top',fontsize=10,color='#536170')
ax.set_xlim(-1,len(t));ax.autoscale_view()
ticks=sorted(set(range(0,len(t),4))|{len(t)-1});ax.set_xticks(ticks,[t.index[i].strftime('%m-%d') for i in ticks])
ax.set_ylabel('美元 / 盎司');ax.grid(alpha=.15);ax.spines[['top','right']].set_visible(False)
ax.set_title(f'伦敦金｜最近{len(t)}个交易日 · {asof}更新',loc='left',fontsize=18,pad=18)
def parse_volume(value):
    value=str(value).replace(',','').strip().upper()
    if value in ('NAN','NONE','-',''):
        return float('nan')
    scale={'K':1e3,'M':1e6,'B':1e9}
    try:
        return float(value[:-1])*scale[value[-1]] if value[-1] in scale else float(value)
    except ValueError:
        return float('nan')
volumes=t.get('Vol.',pd.Series(index=t.index,dtype=float)).map(parse_volume)
report['volume_available_sessions']=int(volumes.notna().sum())
report['volume_note']='Source-reported volume only; missing values are not zero. No futures or tick-volume substitution.'
if volumes.notna().any():
    for i,(_,row) in enumerate(t.iterrows()):
        if pd.notna(volumes.iloc[i]):
            vax.bar(i,volumes.iloc[i],color='#d05252' if row.Price>=row.Open else '#16855d',width=.6)
    vax.set_ylabel('源成交量')
else:
    vax.text(.5,.5,'成交量：Investing XAU/USD 未提供（非零成交量）',ha='center',va='center',transform=vax.transAxes,color='#536170')
    vax.set_yticks([])
vax.grid(alpha=.15);vax.spines[['top','right']].set_visible(False)
(out/'web_candles.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
fig.text(.08,.12,f'最新一根：开 {r.Open:,.2f}   高 {r.High:,.2f}   低 {r.Low:,.2f}   最新 {r.Price:,.2f}',fontsize=11)
fig.text(.08,.075,f'读取北京时间 {stamp[:16].replace("T"," ")}｜网页交易日 {t.index[-1]:%Y-%m-%d}｜该行未提供精确报价时间',fontsize=9,color='#536170')
fig.text(.08,.03,'来源统一为Investing历史行情表；红涨绿跌；完整日线实线、未完成日线虚线。展示数据不参与基准1信号。',fontsize=9,color='#536170')
fig.tight_layout(rect=[0,.17,1,1]);fig.savefig(out/'gold_latest_web_candle.png',dpi=170);plt.close(fig)
print(json.dumps(report,ensure_ascii=False,indent=2))
