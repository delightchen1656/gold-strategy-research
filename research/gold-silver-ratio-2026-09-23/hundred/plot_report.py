import sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from pathlib import Path
import json
import numpy as np
R=Path(__file__).resolve().parent
font=FontProperties(fname='C:/Windows/Fonts/msyh.ttc')
plt.rcParams.update({'axes.unicode_minus':False,'font.size':11,'figure.facecolor':'#f7f8fa','axes.facecolor':'#f7f8fa'})
load=lambda f:json.loads((R/f).read_text(encoding='utf-8'))
fig,(ax,bx)=plt.subplots(1,2,figsize=(15,7.7),gridspec_kw={'width_ratios':[1,1.08]})
fig.subplots_adjust(top=.76,bottom=.24,left=.17,right=.97,wspace=.59)
fig.text(.055,.94,'金银比：100 项研究的两项核心核对',fontproperties=font,fontsize=23,weight='bold',color='#172b4d')
fig.text(.055,.87,'预测增量与条件系数分开看；区间跨零，意味着效应方向仍不确定。',fontproperties=font,fontsize=13,color='#42526e')
results=load('factor_results.json')
spec=[('own','macro','宏观及期权风险'),('macro','ratio','比值及白银波动'),('macro','fund','金银基金持仓')]
for i,(base,model,label) in enumerate(spec):
 r=next(x for x in results if x['target']=='future_logvar20' and x['baseline']==base and x['model']==model and x['metric']=='MSE')
 val=r['change_pct'];lo,hi=r['ci95'];color='#167d9a' if val<0 else '#bf6047'
 ax.errorbar(val,2-i,xerr=[[val-lo],[hi-val]],fmt='o',color=color,capsize=5,markersize=8,lw=2)
 ax.text(val,2-i+.20,f'{val:+.2f}%',ha='center',fontsize=11,color=color)
ax.set_yticks([2,1,0],labels=[x[2] for x in spec],fontproperties=font)
ax.axvline(0,color='#8b99ab',lw=1);ax.set_xlim(-28,18);ax.set_ylim(-.5,2.5)
ax.set_xlabel('未来20日风险预测误差变化（%）',fontproperties=font,labelpad=15)
ax.set_title('样本外：负数表示改善',fontproperties=font,fontsize=14,pad=25,loc='left')
coef=load('factor_coefficients.json')['future_logvar20']['coefficients']
items=[('log_gvz','黄金期权风险 GVZ'),('qret5','比值速度'),('qabs','比值异常幅度'),('g_mm_net_delta','黄金基金净合约变化'),('s_mm_net_delta','白银基金净合约变化')]
for i,(key,label) in enumerate(items):
 r=next(x for x in coef if x['factor']==key);conv=lambda x:100*np.expm1(x/2)
 val=conv(r['beta_std_x']);lo,hi=map(conv,r['ci95']);color='#167d9a' if lo>0 or hi<0 else '#697b92'
 bx.errorbar(val,4-i,xerr=[[val-lo],[hi-val]],fmt='o',color=color,capsize=4,markersize=7,lw=2)
 bx.text(val,4-i+.21,f'{val:+.2f}%',ha='center',fontsize=10,color=color)
bx.set_yticks([4,3,2,1,0],labels=[x[1] for x in items],fontproperties=font)
bx.axvline(0,color='#8b99ab',lw=1);bx.set_xlim(-7,34);bx.set_ylim(-.55,4.6)
bx.set_xlabel('每一标准差对应的模型波动尺度变化（%）',fontproperties=font,labelpad=15)
bx.set_title('多因子：条件关联，非因果',fontproperties=font,fontsize=14,pad=25,loc='left')
for a in [ax,bx]:
 a.spines[['top','right','left']].set_visible(False);a.spines['bottom'].set_color('#ccd3de');a.tick_params(axis='y',length=0);a.grid(axis='x',alpha=.15)
fig.text(.055,.13,'左：509 个信号；首行相对黄金自身历史，其余相对宏观及期权基准。右：753 个信号，控制 17 因子。',fontproperties=font,fontsize=11,color='#42526e')
fig.text(.055,.086,'误差与系数均附边际 95% 区块区间。206 项预测比较整体校正后，没有一项达到 5% 显著水平。',fontproperties=font,fontsize=11,color='#42526e')
fig.text(.055,.042,'美元市场历史研究，非交易胜率或收益承诺。数据、基准定义与缺失限制见最终报告。  2026-09-24',fontproperties=font,fontsize=10,color='#697b92')
fig.savefig(R/'核心结果图.png',dpi=160)
print('Figure saved')
