# 黄金市场研究项目

本项目以伦敦金为价格基准，研究宏观政策、美元与实际利率、市场风险和地缘事件对黄金中期趋势的影响，并通过历史回测筛选兼顾收益与回撤的策略。公开仓库不包含任何个人持仓、订单、盈亏或账户截图。

## 当前基线

基线版本：3.0（2026-09-01；策略2已由DD13替代）

| 策略 | 六字描述 | 实盘映射基金 | 核心逻辑 |
|---|---|---|---|
| 策略1 | 低波趋势控仓 | 008987 | 长趋势成立且波动受控时持仓 |
| 策略2 | 宏观分层增仓 | 009505 | DD13：MA250趋势与三项宏观票分层配置仓位 |
| 策略3 | 美元弱势控仓 | 008702 | 金价趋势与美元弱势共同确认 |

详细参数见 [基线配置](config/baseline_strategies.json)，策略说明见 [基线策略](docs/baseline_strategies.md)。

## 目录结构

```text
gold/
├─ README.md                  项目入口与目录索引
├─ config/                   当前策略、数据源和模型配置
├─ data/                     原始数据、清洗数据、派生结果与匿名示例
├─ scripts/                  数据采集、实验和回测脚本
├─ docs/                     当前研究方法、基线和排行榜说明
├─ reports/                  当前回测及实验结果
├─ research/                 独立研究主题、基准和可视化成果
├─ tools/                    通用辅助工具
└─ private/                  持仓与本地归档（被Git忽略，不上传）
```

## 从哪里开始

- 继续研究策略：先读 [研究方法](docs/methodology.md) 和 [基线策略](docs/baseline_strategies.md)。
- 查看最终候选：读 [综合前十](docs/composite_top10.md) 和 `reports/` 下对应JSON。
- 浏览专题研究：从 [研究索引](research/README.md) 开始。
- 查看图表：打开 [2020至今基线对比](research/strategy-comparisons/图表/新策略123与伦敦金_2020至今折线图.html)。
- 查看策略2的DD13研究来源：读取 [宏观分层增仓](research/strategy-baselines/基准4_宏观三票防守/README.md)。
- 发布前检查：阅读 [隐私与发布检查](docs/privacy.md)。

历史阶段快照、依赖缓存和实盘资料仅保存在本地 `private/`，不属于公开项目内容。

## 常用运行入口

```powershell
python scripts/collect_news.py
powershell -ExecutionPolicy Bypass -File scripts/update_market_data.ps1
python scripts/research_min_hold_7d.py
```

研究脚本生成结果时，应继续写入 `data/derived/` 和 `reports/`。实盘状态只在被 Git 忽略的 `private/` 中维护；公开数据格式示例见 `data/examples/`。

## 研究边界

- 所有信号必须使用当时可获得的信息，避免未来函数。
- 免费行情可能延迟或修订，执行前需要核对数据截止时间。
- 回测计入信号滞后、最低持有期和交易摩擦，但不能保证未来收益。
- 新闻和政治人物言论只能作为可验证事件变量，不能把未经证实的动机作为事实。

本项目属于研究与决策支持，不构成收益承诺或代客交易。
