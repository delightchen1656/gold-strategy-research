import csv
from datetime import datetime
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as md
from matplotlib.font_manager import FontProperties
font=FontProperties(fname='C:/Windows/Fonts/msyh.ttc')
rows=list(csv.DictReader(open('fedfunds-monthly.csv',encoding='utf-8')))
rows=[r for r in rows if r['date'] >= '2000-01-01']
dates=[datetime.fromisoformat(r['date']) for r in rows]
rates=[float(r['rate']) for r in rows]
assert len(rows)==320 and dates[-1]==datetime(2026,8,1)
fig,ax=plt.subplots(figsize=(13,5.8),dpi=170)
fig.patch.set_facecolor('#ffffff')
ax.plot(dates,rates,color='#236b9b',lw=1.8)
ax.fill_between(dates,rates,0,color='#236b9b',alpha=.08)
ax.set_ylim(0,7)
ax.set_xlim(dates[0],datetime(2027,1,1))
ax.xaxis.set_major_locator(md.YearLocator(2))
ax.xaxis.set_major_formatter(md.DateFormatter('%Y'))
ax.set_yticks(range(0,8))
ax.grid(axis='y',color='#dddddd',lw=.6)
ax.spines[['top','right']].set_visible(False)
ax.set_title('美元利率随时间变化｜2000—2026',fontproperties=font,fontsize=20,loc='left',pad=22)
ax.set_ylabel('有效联邦基金利率（年化 %）',fontproperties=font,fontsize=12)
ax.set_xlabel('时间（年）',fontproperties=font,fontsize=12)
i=max(range(len(rates)),key=rates.__getitem__)
ax.scatter([dates[i],dates[-1]],[rates[i],rates[-1]],color='#236b9b',s=25,zorder=4)
ax.annotate(f'{dates[i]:%Y-%m}  {rates[i]:.2f}%',(dates[i],rates[i]),xytext=(15,-4),textcoords='offset points',fontsize=11)
ax.annotate(f'{dates[-1]:%Y-%m}\n{rates[-1]:.2f}%',(dates[-1],rates[-1]),xytext=(-5,18),textcoords='offset points',ha='right',fontsize=11)
fig.text(.085,.045,'口径：有效联邦基金利率，月均值；并非银行美元存款利率或美联储目标区间上限。',fontproperties=font,fontsize=10,color='#555555')
fig.text(.085,.01,'Source: Federal Reserve Board / FRED — FEDFUNDS | Data through 2026-08',fontsize=9,color='#555555')
fig.subplots_adjust(left=.085,right=.97,bottom=.17,top=.84)
fig.savefig('usd-interest-rate-2000.png')
