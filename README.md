# 黄金研究项目

这是一个围绕黄金策略、宏观事件和金银相对价格的可复现研究仓库。当前唯一策略基线是[基准1](research/baseline-1/研究结论.md)；其他专题研究不会自动改变基准策略。

## 当前内容

| 模块 | 状态 | 入口 |
|---|---|---|
| 基准1 | 当前唯一策略 | [研究结论](research/baseline-1/研究结论.md) |
| 基准1每日复核 | 连续更新的压力测试 | [每日研究日志](research/baseline-1/每日研究日志.md) |
| 黄金重大事件图谱 | 持续更新的宏观事件研究 | [事件图谱](research/gold-event-atlas-2023-present/黄金重大事件图谱_2023年至今.md) |
| 美联储利率背景 | 2000年至今的事件研究辅助资料 | [资料说明](research/fed-rates-2000-present/README.md) |
| 金银比研究 | 已完成多轮、100项研究与期限分析 | [专题索引](research/gold-silver-ratio-2026-09-23/README.md) |
| 2026-09-08以前策略 | 历史资料，不参与当前决策 | [归档说明](archive/2026-09-08/README.md) |

基准1使用120日趋势、40日波动率、12%波动率目标、14%回撤退出和月度检查，并增加90日均线偏离保护。D日伦敦AM定盘形成信号，最早映射到D日之后首个可交易的中国基金净值日，严格排除未来信息。

## 目录结构

```text
gold/
├─ config/        当前策略与数据源配置
├─ data/          公共原始数据与质量检查
├─ scripts/       当前基准及数据更新入口
├─ docs/          方法、新闻管线与隐私规范
├─ research/      当前研究成果及其复现材料
├─ archive/       已冻结的历史研究、脚本和旧配置
└─ private/       个人持仓与本地资料（Git忽略）
```

## 运行

```powershell
pip install -r requirements.txt
python scripts/run_baseline_1.py
python scripts/test_baseline_1.py
powershell -ExecutionPolicy Bypass -File scripts/update_market_data.ps1
```

更完整的方法约束见[方法与验证规范](docs/methodology.md)，每日流程见[每日研究规范](docs/daily_research.md)，发布前检查见[隐私规范](docs/privacy.md)。本项目只用于研究与决策支持，历史收益和回撤不代表未来表现。
