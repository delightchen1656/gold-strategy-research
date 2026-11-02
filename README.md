# 黄金研究项目

本仓库分为两套冻结策略、正式维护代码、研究与报告、历史归档四部分。策略研发目前暂停；不自动搜索参数、不自动替换基准，也不执行真实交易。

## 正式策略

基准1和基准2的规则、运行环境、过程记录与保留结果继续独立放在根目录，不生成 ZIP。

| 策略 | 定位 | 独立入口 | 配置 |
|---|---|---|---|
| 基准1 | 每日默认冻结基准 | [基准1说明](基准1/README.md) | [baseline_1.json](config/baseline_1.json) |
| 基准2 | 正式登记的比较基准 | [基准2说明](基准2/README.md) | [baseline_2.json](config/baseline_2.json) |

两个目录均可独立运行，互不读取对方文件。附带运行环境属于本机分发内容，不作为研究源码；策略配置副本必须与 `config/` 中的权威配置保持一致。

## 目录结构

```text
gold/
├─ 基准1/          基准1独立运行、过程记录与保留结果
├─ 基准2/          基准2独立运行、过程记录与保留结果
├─ config/         两套冻结策略及公共数据源配置
├─ scripts/
│  ├─ core/        冻结信号和执行核心
│  ├─ daily/       正式日更入口
│  ├─ data/        公共数据采集
│  ├─ reporting/   当前报告与图表工具
│  └─ validation/  正式行为测试
├─ research/       研究记录、数据快照和专题报告（路径保留）
├─ reports/        汇总报告（路径保留）
├─ docs/           项目架构、方法和隐私规范
├─ archive/        冻结历史，只用于审计追溯
└─ private/        个人持仓与本地资料，Git忽略
```

完整边界见[项目架构](docs/architecture.md)。

## 正式命令

```powershell
python scripts/daily/update_active_baseline.py YYYY-MM-DD
python scripts/daily/daily_web_candles.py YYYY-MM-DD
python scripts/validation/test_baseline_signal.py
powershell -ExecutionPolicy Bypass -File scripts/update_market_data.ps1
```

基准1仍是每日默认；基准2用于独立比较，登记它不表示自动切换。完整日线信号采用已完成的 Europe/London 日线，个人交易计划不得进入公开研究。

## 研究与报告入口

| 模块 | 权威入口 |
|---|---|
| 黄金重大事件与完整宏观研究 | [黄金重大事件图谱](research/gold-event-atlas-2023-present/黄金重大事件图谱_2023年至今.md) |
| 黄金宏观检查规则 | [研究规则](research/gold-macro-monitor/研究规则.md) |
| 机构预测与实绩 | [综合报告](research/gold-event-atlas-2023-present/机构黄金预测与实绩综合报告.md) |
| 基准日度研究记录 | [每日研究日志](research/baseline-1/每日研究日志.md) |
| 基准1与基准2汇总 | [多区间及年度报告](reports/基准1与基准2_多区间及年度回测报告_截至2026-10-29.md) |
| 金银比专题 | [专题索引](research/gold-silver-ratio-2026-09-23/README.md) |

阶段报告、失败实验和旧脚本只在 `archive/` 中追溯，不是当前入口。历史区间已经被观察，不能称为全新样本外验证。
