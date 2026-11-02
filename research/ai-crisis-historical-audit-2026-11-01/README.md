# 五条件历史核验数据

执行日期2026-11-01。正式分析统一追加黄金重大事件图谱；本目录只放计算、原始序列和方法说明。

- calculate.py重算results.json、event_results.csv、就业计算及三段黄金日序列。
- PAYEMS、UNRATE为FRED当前修订历史，https://fred.stlouisfed.org/graph/fredgraph.csv?id=PAYEMS&cosd=1996-01-01&coed=2021-12-31 （UNRATE同式）。非当时版本。单位就业千人、失业率%。
- 条件5：非农月差的3月均值<0，且失业率3月均值较前12个月3月均值最低值高至少0.5个百分点。当前月不进入比较基准。浮点容差1e-9。
- sahm.csv为FRED SAHMREALTIME，独立参考，不能完全替代自定义条件5，也没有证明历史每次发布的首次同时满足日期。
- HY历史请求失败：BAMLH0A0HYM2.csv及hy_vintage.csv实际只包含2023-10-31以后，虽然请求1996—2021。FRED目前仅供近3年，故不用于历史条件3；不存在已计算500bp连续5日的历史触发日。dbnomics亦404。不用其他利差冒充原序列。
- STLFSI4为背景序列，不代替条件4机构级证据。
- gold来自前一图表保存的GoldPrice.com daily CSV（CC BY4.0，https://www.goldprice.com/gold-price-history.csv），历史早段为LBMA定盘、2015后该站标为Metals.dev日值。不同年代并非严格同一日界。价格为日值，不是盘中低点。原始SHA256写在results.json。
- 事件锚点：2000-09-22 Intel预警后股价急跌；2008-09-15雷曼；2020-03-09市场急跌。均为事后选取，不是算法预测。各自之后一年内最低日值是事后描述，非最优可交易底部；分段极值涨跌也不能作为策略收益。
- 原AI-CRISIS-v1前两项及第三项事件分支包含AI字样，不能在这些年份套用；按科技/房贷/疫情替换只能叫历史机制映射，不是原模型成功回测。
- 未构建非危机对照、未校准权重、未补齐财报/公布时点面板，不给胜率、精确危机概率或综合触发计数。
- bls_200106_release.pdf下载成功，来源FRASER BLS历史存档；本机PDF解析依赖缺失，未把全文解析完成或逐项验证当作已完成。
