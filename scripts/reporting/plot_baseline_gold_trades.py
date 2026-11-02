"""London AM with baseline fund execution-date markers, not gold fills."""
import io
import json
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

ROOT=Path(__file__).resolve().parents[2]
latest=json.loads((ROOT/'research/baseline-1/latest_signal.json').read_text(encoding='utf-8'))
source=(ROOT/latest['report']).parent
out=ROOT/'research/baseline-1/gold-trade-markers'
out.mkdir(exist_ok=True)
gold=pd.read_csv(ROOT/'research/baseline-1/inputs/gold.csv',parse_dates=['date']).set_index('date').gold_usd
table=pd.read_html(io.StringIO((source/'gold.raw').read_text(encoding='utf-8')))[0]
table.columns=['date','price']
table['date']=pd.to_datetime(table.date,format='%d. %B %Y',errors='coerce')
table['price']=pd.to_numeric(table.price.astype(str).str.replace(',',''),errors='coerce')
extra=table.dropna().set_index('date').price.sort_index()
gold=pd.concat([gold,extra[extra.index>gold.index.max()]]).loc['2021-01-04':latest['signal_date']]
assert gold.index.is_unique
daily=pd.read_json(source/'fund_daily.json',orient='table')
trades=json.loads((source/'fund_trades.json').read_text(encoding='utf-8'))
points=[]
for t in trades:
    d=pd.Timestamp(t['date'])
    if d<gold.index.min() or d>gold.index.max():continue
    quote=gold.loc[:d].iloc[-1]
    quotedate=gold.loc[:d].index[-1]
    points.append({**t,'plot_gold_am':float(quote),'quote_date':str(quotedate.date()),
                   'actual_weight_after':float(daily.loc[d,'weight'])})
plt.rcParams['font.sans-serif']=['Microsoft YaHei','SimHei']
plt.rcParams['axes.unicode_minus']=False
fig,(ax,pos)=plt.subplots(2,1,figsize=(16,9),sharex=True,gridspec_kw={'height_ratios':[3.5,1]},facecolor='#fafbfd')
ax.plot(gold.index,gold.values,color='#b88a27',lw=1.7,label='伦敦金 AM 定盘')
for side,marker,color,label in [('buy','^','#16855d','▲ 买入 / 加仓'),('sell','v','#d05252','▼ 卖出 / 减仓')]:
    rows=[p for p in points if p['side']==side]
    ax.scatter(pd.to_datetime([p['date'] for p in rows]),[p['plot_gold_am'] for p in rows],
               marker=marker,s=76,c=color,edgecolors='white',linewidths=.65,zorder=4,label=f'{label}（{len(rows)}次）')
ax.set_title('伦敦金走势 × 基准1买卖记录',loc='left',fontsize=22,pad=18)
ax.set_ylabel('美元 / 盎司')
ax.legend(loc='upper left',ncol=3,frameon=False)
pos.fill_between(daily.index,daily.weight*100,step='post',color='#506f91',alpha=.22)
pos.step(daily.index,daily.weight*100,where='post',color='#506f91',lw=1.2)
pos.set_ylabel('模拟仓位（%）')
pos.set_ylim(-4,105);pos.set_yticks([0,50,100])
pos.xaxis.set_major_locator(mdates.YearLocator());pos.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
pos.xaxis.set_minor_locator(mdates.MonthLocator(bymonth=[4,7,10]))
for a in (ax,pos):
    a.set_facecolor('#fafbfd');a.grid(alpha=.16);a.spines[['top','right']].set_visible(False)
ax.set_xlim(gold.index.min(),gold.index.max()+pd.Timedelta(days=30))
fig.text(.07,.065,f'2021-01-04 至 {gold.index[-1]:%Y-%m-%d}  |  基准1按建信A模拟执行记录标记；不是个人账户实盘。',fontsize=11,color='#536170')
fig.text(.07,.035,'三角所在日期为基金成交净值归属日，早于该日的伦敦AM数据形成信号；三角纵坐标仅对照金价，不代表基金成交价。',fontsize=10,color='#536170')
fig.text(.07,.012,'无定盘日使用此前最近定盘作图；下图为基金模拟实际仓位，包含价格漂移。',fontsize=10,color='#536170')
fig.tight_layout(rect=[0,.09,1,1])
fig.savefig(out/'london_gold_baseline1_trades.png',dpi=180)
fig.savefig(out/'london_gold_baseline1_trades.svg')
(out/'markers.json').write_text(json.dumps({'source':str(source),'markers':points},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'output':str(out),'cutoff':str(gold.index[-1].date()),'markers':len(points),'missing_fix_dates':[p['date'] for p in points if p['date']!=p['quote_date']]},ensure_ascii=False))
