from pathlib import Path
import sys
import json
sys.path.insert(0, str(Path.home() / '.cache/codex-gold-research-pydeps'))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

ROOT = Path(__file__).resolve().parent
font_manager.fontManager.addfont('C:/Windows/Fonts/msyh.ttc')
plt.rcParams.update({'font.family': 'Microsoft YaHei', 'axes.unicode_minus': False,
                     'font.size': 11, 'axes.spines.top': False, 'axes.spines.right': False,
                     'axes.spines.left': False, 'axes.spines.bottom': False})
j = json.loads((ROOT / 'round1_results.json').read_text(encoding='utf-8'))
states = {r['state']: r for r in j['states']}
features = ['speed', 'acceleration', 'raw_shock', 'residual_shock', 'asymmetric_shock']
labels = ['变化速度', '变化加速度', '原始异常幅度', '剔除共同因素后的异常', '正负异常分别加入']
rows = [next(r for r in j['results'] if r['period'] == 'all' and r['target'] == 'future_vol20' and r['model'] == k) for k in features]
fig, ax = plt.subplots(1, 2, figsize=(14, 8.7), gridspec_kw={'width_ratios': [1, 1.12]})
fig.set_facecolor('#f7f8fa')
for a in ax:
    a.set_facecolor('#f7f8fa')
    a.set_axisbelow(True)
    a.tick_params(length=0)
fig.subplots_adjust(left=.07, right=.96, top=.76, bottom=.27, wspace=.65)
fig.text(.06, .925, '金银比：同期市场状态与预测增量', fontsize=23, weight='bold', color='#12263a')
fig.text(.06, .871, '观察风险环境有帮助；本次简单指标尚未提供稳定的额外预测信息', fontsize=13, color='#536578')

x = np.arange(2)
g = [states[k]['mean_gold_5d_pct'] for k in ['ratio_up_fast', 'ratio_down_fast']]
s = [states[k]['mean_silver_5d_pct'] for k in ['ratio_up_fast', 'ratio_down_fast']]
ax[0].bar(x - .18, g, .32, label='黄金', color='#bd8b2e')
ax[0].bar(x + .18, s, .32, label='白银', color='#7594af')
ax[0].axhline(0, color='#b3bdc8', linewidth=1)
ax[0].set_ylim(-10, 10)
ax[0].set_xticks(x, ['比值异常上行\n43个周观察', '比值异常下行\n60个周观察'])
ax[0].set_ylabel('已发生的5日平均收益（%）', labelpad=12)
ax[0].grid(axis='y', color='#e2e7ec')
ax[0].set_title('同期：黄金相对强，不代表黄金上涨', loc='left', pad=27, fontsize=13, weight='bold')
ax[0].legend(loc='upper center', bbox_to_anchor=(.5, 1.035), ncol=2, frameon=False)
for positions, values in [(x - .18, g), (x + .18, s)]:
    for position, value in zip(positions, values):
        ax[0].text(position, value + (.45 if value > 0 else -.5), f'{value:+.2f}%', ha='center', va='bottom' if value > 0 else 'top', fontsize=11, color='#263b4e')

means = np.array([r['mse_change_pct'] for r in rows])
lo = np.array([r['ci95_pct'][0] for r in rows])
hi = np.array([r['ci95_pct'][1] for r in rows])
y = np.arange(len(rows))
ax[1].axvspan(-3, 0, color='#edf3ef', zorder=-2)
ax[1].axvline(0, color='#82909d', linestyle='--', linewidth=1)
ax[1].errorbar(means, y, xerr=np.stack([means-lo, hi-means]), fmt='o', color='#285779', ecolor='#809bb1', capsize=4, markersize=7, linewidth=2)
ax[1].set_yticks(y, labels)
ax[1].invert_yaxis()
ax[1].set_ylim(4.8, -.8)
ax[1].set_xlim(min(-1, np.floor(lo.min()*2)/2-.2), max(2, np.ceil(hi.max()*2)/2+.2))
ax[1].set_xlabel('未来20日黄金波动预测误差变化（%）\n负值为改善，正值为变差', labelpad=13)
ax[1].grid(axis='x', color='#e2e7ec')
ax[1].set_title('预测：加入GVZ后，比值增量不稳健', loc='left', pad=27, fontsize=13, weight='bold')
for yy, v in zip(y, means):
    ax[1].annotate(f'{v:+.2f}%', (v, yy), xytext=(7, 9), textcoords='offset points', fontsize=10, color='#285779')

fig.text(.06, .175, '更强的比较基准：黄金自身历史 + 美元、实际利率、美股、VIX + 黄金期权隐含波动GVZ。', fontsize=11, color='#354d61')
fig.text(.06, .133, '左图按已发生的比值异动分组，含数学选择效应，不能当作未来收益或上涨概率。', fontsize=10, color='#667687')
fig.text(.06, .096, '右图含584次周度预测（2014-09至2025-11）；横线为95%区块重采样区间，没有一项支持稳定改善。', fontsize=10, color='#667687')
fig.text(.06, .052, '来源：GLD/SLV价格、Cboe及宏观公开数据；本次独立计算。研究日期：2026-09-23。', fontsize=9, color='#7f8a96')
fig.savefig(ROOT / '三轮研究核心图.png', dpi=180, facecolor=fig.get_facecolor())
print(json.dumps({'chart': str(ROOT / '三轮研究核心图.png'), 'risk_20d': rows}, ensure_ascii=False, indent=2))
