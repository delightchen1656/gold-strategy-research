# 隐私与发布检查

本仓库只公开研究代码、策略参数、公共行情数据和回测结果。真实本金、持仓市值、份额、盈亏、订单、账户截图与实盘工作簿统一保存在根目录的 `private/`，该目录已被 Git 忽略。

## 本地私有目录

```text
private/
├─ portfolio/       当前组合、流水与实盘说明
├─ workbooks/       实盘工作簿、截图和检查文件
├─ outputs/         每日维护输出
└─ tools/           含真实账户数据的本地生成工具
```

`data/examples/current_portfolio.example.json` 仅用于展示数据格式，数值均为空值或零，不是真实账户。

## 上传前检查

```powershell
git status --short
git check-ignore -v private/data/current_portfolio.json
git grep -n -I -E "(current_market_value|unrealized_pnl|confirmed_shares|订单编号|当前持仓)"
```

提交前应检查 `git status` 的完整文件清单。不要使用 `git add -f` 强制加入被忽略文件。如果私密文件曾进入 Git 历史，仅添加 `.gitignore` 不够，还需在发布前重写历史或新建干净仓库。
