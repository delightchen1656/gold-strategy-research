"""Plot a dated, user-requested web quote independently of historical OHLC."""
import json
from io import StringIO
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

root=Path(__file__).resolve().parents[2]
out=root/'research/baseline-1/update-2026-10-23'
quote={'source':'https://www.kitco.com/charts/gold','bid':4023.60,'ask':4025.60,
       'quote_time_beijing':'2026-10-23 04:57–04:58','note':'Dated web snapshot; not a live feed or OHLC bar.'}
(out/'kitco_web_quote.json').write_text(json.dumps(quote,ensure_ascii=False,indent=2),encoding='utf-8')
t=pd.read_html(StringIO((out/'xauusd_chartexchange.raw').read_text(encoding='utf-8')))[0]
t=t.rename(columns={'Date (UTC)':'date','Open':'open','High':'high','Low':'low','Close':'close'})
t.index=pd.to_datetime(t['date'])
t=t.loc['2026-09-24'<=t.index].sort_index().loc[:'2026-10-22']
plt.rcParams['font.sans-serif']=['Microsoft YaHei','SimHei']
plt.rcParams['axes.unicode_minus']=False
fig,ax=plt.subplots(figsize=(12,6.3),facecolor='#fafbfd')
ax.set_facecolor('#fafbfd')
for i,(d,r) in enumerate(t.iterrows()):
    pending=d==pd.Timestamp('2026-10-22')
    color='#d05252' if r.close>=r.open else '#16855d'
    ax.vlines(i,r.low,r.high,color=color,linestyles='--' if pending else '-',alpha=.45 if pending else 1)
    ax.add_patch(Rectangle((i-.28,min(r.open,r.close)),.56,max(abs(r.close-r.open),.2),
                 facecolor='none' if pending else color,edgecolor=color,linestyle='--' if pending else '-',alpha=.45 if pending else 1))
    if pending:
        ax.annotate('旧分时快照',xy=(i,r.high),xytext=(-20,15),textcoords='offset points',ha='center',fontsize=9,color='#677583')
ax.axhline(quote['bid'],color='#16855d',ls='--',lw=1.3)
ax.scatter([len(t)-1],[quote['bid']],color='#16855d',s=40,zorder=4)
ax.annotate('Kitco 买价 4,023.60',xy=(len(t)-1,quote['bid']),xytext=(-12,-24),textcoords='offset points',ha='right',color='#16855d',fontsize=12,fontweight='bold')
ax.set_xlim(-1,len(t)+.5)
ax.set_ylim(min(t.low.min(),quote['bid'])-35,t.high.max()+25)
ticks=sorted(set(list(range(0,len(t),5))+[len(t)-1]))
ax.set_xticks(ticks,[t.index[i].strftime('%m-%d') for i in ticks])
ax.set_ylabel('美元 / 盎司');ax.grid(alpha=.15);ax.spines[['top','right']].set_visible(False)
ax.set_title('伦敦金｜近30自然日K线 + 网页最新报价',loc='left',fontsize=18,pad=20)
fig.text(.08,.12,'网页快照：北京时间 10月23日 04:57—04:58｜买价 4,023.60 / 卖价 4,025.60',fontsize=11)
fig.text(.08,.075,'实线K线截至10月21日；虚线K线为10月22日13:30旧快照；横虚线为Kitco最新买价。',fontsize=10,color='#536170')
fig.text(.08,.03,'K线：ChartExchange，UTC日界线，涨红跌绿。报价：Kitco，独立标记，不拼接OHLC、不参与基准1信号。',fontsize=9,color='#536170')
fig.tight_layout(rect=[0,.17,1,1])
fig.savefig(out/'gold_web_quote.png',dpi=170)
plt.close(fig)
