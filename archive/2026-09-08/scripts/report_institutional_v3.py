from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'research'/'institutional-v3-2026-09-08'
d=json.loads((OUT/'result.json').read_text(encoding='utf-8'))
s=d['selected']['spec']
lines=['# 机构化黄金策略 V3','',
       '数据截止至2026-09-04。候选只按2021—2024排序；2025年至今只作为冻结后否决检验，不用于提高排名。参数表为1,152行，预2025存在441条独立目标仓位路径；参数行排名不等于独立策略排名。','',
       '## 部署参数','',
       '| 项目 | 参数 |','|---|---:|',
       f'| 趋势窗口 | {s["horizon"]}个伦敦金观察日 |',
       '| 波动率窗口 | 40个交易日 |',
       f'| 波动率目标 | {s["vol_target"]:.0%} |',
       f'| 最高仓位 | {s["cap"]:.0%} |',
       f'| 回撤退出 | 距{ s["horizon"] }日高点{ s["stop"]:.0%} |',
       f'| 检查频率 | 月度；调仓带{ s["band"]:.0%} |',
       f'| 冷静期 | {s["cooldown"]}个伦敦观察日 |','',
       '内部部署预算为每个产品、每个阶段最大回撤低于13%、平均实际仓位不高于65%，为用户的15%和70%硬约束保留余量。','',
       '## 分阶段结果（已扣费）','',
       '| 产品 | 阶段 | 年化收益 | 最大回撤 | 平均仓位 | 交易日数 |', '|---|---|---:|---:|---:|---:|']
for product,label in [('cmb','积存金代理'),('fund','建信上海金ETF联接A')]:
 for stage,m in d['selected']['full'][product]['splits'].items():
  lines.append(f'| {label} | {stage} | {m["cagr_pct"]:.2f}% | {m["max_drawdown_pct"]:.2f}% | {m["average_weight_pct"]:.2f}% | {m["trade_days"]} |')
lines += ['', '## 全期结果','', '| 产品 | 年化收益 | 最大回撤 | 平均仓位 | 总费用 |', '|---|---:|---:|---:|---:|']
for product,label in [('cmb','积存金代理'),('fund','建信上海金ETF联接A')]:
 m=d['selected']['full'][product]['full']
 lines.append(f'| {label} | {m["cagr_pct"]:.2f}% | {m["max_drawdown_pct"]:.2f}% | {m["average_weight_pct"]:.2f}% | {m["fees_cny"]:.2f}元 |')
lines += ['', '## 压力检验','', '| 情景 | 内部预算通过 |', '|---|---|']
labels={'one_extra_session_delay':'额外延迟一个交易日','cmb_double_spread':'积存金点差加倍','cmb_double_spread_and_0_1pct_slippage':'积存金点差加倍且单边滑点0.1%','fund_standard_1_5pct_subscription_fee':'建信A申购费按1.5%','fund_t7_settlement':'建信A赎回资金T+7可用'}
for k,v in d['stress'].items():lines.append(f'| {labels[k]} | {"通过" if v["internal_budget_pass"] else "未通过"} |')
lines += ['', '## 仍需在实盘前持续验证','', '- 积存金使用伦敦金与汇率换算后的人民币金价代理；缺少历史客户成交价。', '- 回测不能证明未来回撤；达到13%风险线时应暂停加仓并重新审查，不把15%当作日常运行目标。', '- 每月复核数据完整性、基金申赎状态和支付宝费率；只有在规则变化时重新回测。']
(OUT/'研究结论.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print((OUT/'研究结论.md').resolve())

