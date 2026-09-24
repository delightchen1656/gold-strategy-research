from pathlib import Path
import json
import numpy as np
R=Path(__file__).resolve().parent
a=json.loads((R/'outlook_snapshot.json').read_text(encoding='utf-8'))
a['macro_web_checks']={'real_yield':{'date':'2026-09-22','percent':2.63,'source':'https://fred.stlouisfed.org/series/DFII10','access':'网页，CSV请求超时；未计算20日真实利率变化'},
 'fed_statement':{'date':'2026-09-16','change_bp':25,'target_range_percent':[3.75,4.00],'source':'https://www.federalreserve.gov/newsevents/pressreleases/monetary20260916a.htm'},
 'fed_projection':{'date':'2026-09-16','2026_median':4.1,'2027_median':4.1,'source':'https://www.federalreserve.gov/monetarypolicy/fomcprojtabl20260916.htm','note':'参与者适当政策路径判断，不是承诺或市场概率。'}}
lines=['# 金银比研究应用：未来1、3、6、12个月','', '分析时点：2026-09-24。日线采用截至 9 月 23 日的完整交易日。主要回答从现在起的未来期限，同时提供过去对应期限，避免把回顾和预测混用。', '',
 '**判断：短期价格结构偏弱，中期仍属震荡；半年和一年方向没有足够证据作强判断。金银比在这些期限主要提供相对强弱和状态核对，不能单独给出黄金价格目标。**','',
 '**当前参考值及来源**','',
 '9 月 24 日美东 06:18（北京时间 18:18）的交易商指示性现货报价：黄金 4,249.90 美元/盎司、白银 63.54，比值约 66.89。不同报价商及时点会有差别。[报价页](https://invest.alexlexington.com/spot-prices)','',
 'CBOE 本次下载的 GVZ 历史文件最新为 9 月 22 日 23.59，即约 23.59% 的年化隐含波动读数。它衡量约 30 天 GLD 期权风险，不提供未来一年完整波动率曲线。[CBOE 历史数据](https://www.cboe.com/tradable-products/vix/vix-historical-data)','',
 '**过去发生了什么**','',
 '下表使用同收盘口径 GLD/SLV 调整价格作为金银涨跌代理，计算普通收益及二者价格比的变化；ETF每份价格比的绝对水平不等于现货金银比。1个月起点因休市落在8月21日，其余起点为6月23日、3月23日和上一年9月23日。GC/SI连续期货也作方向交叉核对，不能把不同结算工具拼成精确现货收益。', '',
 '| 过去期限 | 黄金代理 | 白银代理 | 相对比值变化 |','|---|---:|---:|---:|']
for m in [1,3,6,12]:
 g=a['symbols']['GLD']['returns_pct'][str(m)]['pct'];s=a['symbols']['SLV']['returns_pct'][str(m)]['pct'];q=a['relative_return'][str(m)]
 lines.append(f'| {m}个月 | {g:+.2f}% | {s:+.2f}% | {q:+.2f}% |')
lines+=['','过去一个月金银都跌约7%，比值近乎不动，说明共同下跌可以被比值完全遮住；过去半年比值上升，但黄金也下跌，说明“黄金相对抗跌”不等于黄金正收益。', '',
 '最近5个交易日比值对数变化约−1.64%，相对于此前252日尺度的标准分约−0.18；本指标没有显著异常。该标准分可能受过去极端行情抬高尺度影响，不能解释成市场绝对平静。日线由公开行情端点下载，原始快照、下载时间和哈希见本目录 sources_metadata.json；原始来源为 [GLD历史](https://finance.yahoo.com/quote/GLD/history/) 与 [SLV历史](https://finance.yahoo.com/quote/SLV/history/)。','',
 '**趋势判断依据及可改变判断的条件**','',
 '截至9月23日，GLD低于20日均线约2.34%、低于200日均线约5.64%，在60日均线上方约0.44%；美元指数近一个月上涨约2.33%。这些事实支持“短期偏弱，中期震荡”的描述，没有给出经验证的未来胜率。','',
 '美联储9月16日加息25个基点至3.75%—4.00%；9月预测中的2026、2027年末政策利率中位数均约4.1%，所以不能预先把持续降息作为半年／一年看多的默认前提。[美联储决议](https://www.federalreserve.gov/newsevents/pressreleases/monetary20260916a.htm)、[政策预测](https://www.federalreserve.gov/monetarypolicy/fomcprojtabl20260916.htm)。10年实际收益率最近可核对值为9月22日2.63%；没有从此次下载取得完整更新序列，因此不宣称其20日趋势已确认。[FRED](https://fred.stlouisfed.org/series/DFII10)','',
 '相反的支持因素仍然存在：世界黄金协会9月报告记录8月较强ETF流入，并讨论财政信誉风险对黄金需求的支持。这是条件性渠道，并不保证未来收益。[原报告](https://www.gold.org/goldhub/research/gold-market-commentary-august-2026)','',
 '| 未来期限 | 当前定性倾向 | 金银比可提供的指导 | 方向把握 |','|---|---|---|---|',
 '| 1个月 | 偏弱震荡，警惕反弹后继续回落 | 区分金价自身压力与银价更弱；急变配合GVZ检查风险 | 中低 |',
 '| 3个月 | 震荡，修复是否成立待价格和宏观确认 | 核对相对强弱是否持续；不能根据单次急升押黄金反弹 | 低 |',
 '| 半年 | 保留双向情景，尚未确认新上升趋势 | 辅助区分工业周期与黄金特有需求，降低对固定中枢的依赖 | 低 |',
 '| 一年 | 以宏观情景判断，不能给单边高置信预测 | 更多用于相对配置和结构变化分析，不能用67或历史均值反推金价 | 低 |','',
 '**区间猜测：可复算的波动示意带**','',
 '为避免把样本内回归系数强行当成价格预测，本表采用中性中心：P0=4,249.90，零对数趋势、波动不变，区间=P0×exp(±1.28155×0.2359×√T)，T为年。它在正态对数收益假设内部对应中央80%的期末区间，但没有验证真实80%覆盖率；并非估值区间、支撑阻力或期间最高最低价。定性短期偏弱判断没有另加人为漂移到公式里。半年／一年尤其只是延长当前30天风险水平的量级演示。', '',
 '| 未来期限 | 当前波动假设下期末区间，美元/盎司 | 相对现价范围 | 若年化波动改为35%的情景 |','|---|---:|---:|---:|']
for b in a['bands']:
 lo,hi=b['lower'],b['upper'];assert lo<a['quote_anchor']['gold_usd_oz']<hi
 assert np.isclose(lo*hi,a['quote_anchor']['gold_usd_oz']**2)
 lines.append(f"| {b['months']}个月 | {round(lo/10)*10:,}—{round(hi/10)*10:,} | {100*(lo/4249.9-1):+.1f}%—{100*(hi/4249.9-1):+.1f}% | {round(b['lower_35vol']/10)*10:,}—{round(b['upper_35vol']/10)*10:,} |")
lines+=['','35%是明确假设的更高波动情景，不是由金银比估计的概率或确定压力上限。跳跃、波动变化和价格趋势都可能突破这些带；长时间跨度的真实不确定性不只来自今天的波动水平。','',
 '**使用时的三个判断顺序**','',
 '1. 先看黄金自身是否站回20日、60日及200日均线，再看美元与实际利率是否配合。均线是趋势描述工具，不是已证明获利的交易规则。',
 '2. 比值升而黄金跌，优先解释为“黄金相对白银抗跌”，不能直接转成买入理由；比值降且黄金涨，也可以是黄金上涨中的白银更强。',
 '3. 若美元和实际利率转弱、黄金价格结构改善，并有持续需求确认，中长期判断可以转多；若美元、实际利率走强且黄金持续弱于长期均线，判断应偏向下行。比值只作配合证据。','',
 '前100项研究没有建立金银比的稳定单边预测优势，本补充不把同一研究改写成有精确胜率的价格模型。区间计算和趋势判断的证据等级不同，应分别使用。']
(R/'期限与区间分析.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
(R/'outlook_snapshot.json').write_text(json.dumps(a,ensure_ascii=False,indent=2),encoding='utf-8')
print('Outlook note written; horizon band arithmetic verified.')
