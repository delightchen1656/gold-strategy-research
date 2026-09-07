import csv
from datetime import datetime
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as md
from matplotlib.font_manager import FontProperties
from matplotlib.patches import Patch
font=FontProperties(fname='C:/Windows/Fonts/msyh.ttc')
rows=[r for r in csv.DictReader(open('fedfunds-monthly.csv',encoding='utf-8')) if r['date']>='2000-01-01']
dates=[datetime.fromisoformat(r['date']) for r in rows]
rates=[float(r['rate']) for r in rows]
# 2000-2024: U.S. Global Investors, GROW Q2 2025 slides, rounded annual averages.
# 2025: World Gold Council, Full Year 2025, LBMA PM annual average.
gold=[279,271,310,363,409,444,604,695,872,972,1225,1572,1669,1411,1266,1160,1251,1257,1268,1392,1770,1799,1800,1943,2388,3431.5]
fig,(ax,bx)=plt.subplots(2,1,figsize=(14,8),dpi=160,sharex=True,gridspec_kw={'height_ratios':[1,1.5]})
for i,(d,r) in enumerate(zip(dates,rates)):
    end=dates[i+1] if i+1<len(dates) else datetime(2026,9,1)
    color='#f4d4c6' if r>=4 else '#d9e9f7' if r<=1 else None
    if color:
        for a in (ax,bx): a.axvspan(d,end,color=color,alpha=.65,lw=0)
ax.plot(dates,rates,color='#28658b',lw=2)
ax.axhline(4,color='#b46141',ls=':',lw=1)
ax.axhline(1,color='#6d99ba',ls=':',lw=1)
ax.set_ylim(0,7)
ax.set_ylabel('美元利率（年化 %）',fontproperties=font,fontsize=12)
ax.set_title('2000年至今：高、低利率阶段与黄金价格',fontproperties=font,fontsize=21,loc='left',pad=20)
ax.legend(handles=[Patch(facecolor='#f4d4c6',label='高利率：≥4%'),Patch(facecolor='#d9e9f7',label='低利率：≤1%'),Patch(facecolor='white',edgecolor='#bbb',label='其余：1%—4%')],prop=font,loc='upper right',ncol=3,frameon=False)
gd=[datetime(y,7,1) for y in range(2000,2026)]
bx.plot(gd,gold,color='#b58a22',marker='o',ms=4,lw=2,label='2000—2025年：黄金年度均价')
bx.scatter([datetime(2026,9,4)],[4419.09],marker='D',color='#8b5e14',s=42,zorder=4)
bx.annotate('2026-09-04 盘中报价\n4,419美元（非年均价）',(datetime(2026,9,4),4419.09),xytext=(-8,12),textcoords='offset points',ha='right',fontproperties=font,fontsize=10)
for year in [2000,2006,2007,2012,2015,2021,2023,2024,2025]:
    k=year-2000
    bx.annotate(f'{gold[k]:,.0f}',(gd[k],gold[k]),xytext=(0,9 if year!=2006 else -17),textcoords='offset points',ha='center',fontsize=9,color='#684f19')
bx.set_ylim(0,5100)
bx.set_ylabel('黄金价格（美元/金衡盎司）',fontproperties=font,fontsize=12)
bx.legend(prop=font,loc='upper left',frameon=False)
bx.xaxis.set_major_locator(md.YearLocator(2))
bx.xaxis.set_major_formatter(md.DateFormatter('%Y'))
bx.set_xlim(datetime(2000,1,1),datetime(2027,2,1))
for a in (ax,bx):
    a.spines[['top','right']].set_visible(False)
    a.grid(axis='y',alpha=.2)
fig.text(.075,.065,'口径：利率为有效联邦基金利率月均值，截至2026年8月；高低阈值仅用于本图比较。',fontproperties=font,fontsize=10,color='#555')
fig.text(.075,.038,'金价为名义美元价格，未经通胀调整。年度均价会平滑年内涨跌；2026年报价不与年均线连接。',fontproperties=font,fontsize=10,color='#555')
fig.text(.075,.012,'Sources: FRED FEDFUNDS; U.S. Global Investors (2000–2024); World Gold Council (2025); Reuters (2026-09-04 17:49 UTC).',fontsize=8,color='#666')
fig.subplots_adjust(left=.075,right=.97,top=.9,bottom=.13,hspace=.15)
fig.savefig('gold-vs-rates-2000.png')
