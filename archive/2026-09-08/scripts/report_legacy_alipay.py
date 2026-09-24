"""Render the three original strategies under the confirmed Alipay rules."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research/execution-v2-2026-09-07"
NAMES = ["策略1：60日价格通道突破", "策略2：252日动量＋60日波动率", "策略3：MA90宏观状态"]
PRODUCTS = {"cmb": "积存金代理", "fund": "建信A（支付宝）"}


def main():
    report = json.loads((OUT / "result.json").read_text(encoding="utf-8"))
    lines = [
        "# 原三策略：支付宝规则重跑",
        "",
        "统一使用支付宝截图确认的规则：申购费0.15%，T日15:00前申请按T日净值，T+1确认，确认后下一交易日可卖，卖出后T+1进入余额宝可用。积存金路径不变。",
        "",
        "## 全期结果",
        "",
        "| 策略 | 产品 | 全期收益 | 年化收益 | 最大回撤 | 平均仓位 | 期末资产 | 买卖次数 | 费用 | 三阶段均合格 |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for name, item in zip(NAMES, report["baselines"][:3]):
        for path, value in item["results"].items():
            m = value["full"]
            lines.append(
                f"| {name} | {PRODUCTS[path]} | {m['return_pct']:.2f}% | {m['cagr_pct']:.2f}% | "
                f"{abs(m['max_drawdown_pct']):.2f}% | {m['average_weight_pct']:.2f}% | {m['final_cny']:,.2f}元 | "
                f"{m['trade_days']} | {m['fees_cny']:,.2f}元 | {'是' if item['eligible_all_stages'] else '否'} |"
            )
    lines += ["", "## 阶段结果", "", "| 策略 | 产品 | 阶段 | 收益 | 最大回撤 | 平均仓位 | 买卖次数 | 费用 |", "|---|---|---|---:|---:|---:|---:|---:|"]
    for name, item in zip(NAMES, report["baselines"][:3]):
        for path, value in item["results"].items():
            for stage, m in value["splits"].items():
                lines.append(
                    f"| {name} | {PRODUCTS[path]} | {stage} | {m['return_pct']:.2f}% | "
                    f"{abs(m['max_drawdown_pct']):.2f}% | {m['average_weight_pct']:.2f}% | "
                    f"{m['trade_days']} | {m['fees_cny']:,.2f}元 |"
                )
    lines += [
        "",
        "策略1和策略3均因至少一个产品、至少一个阶段的最大回撤超过15%而不合格；策略2继续合格。",
        "",
    ]
    (OUT / "原三策略_支付宝规则重跑.md").write_text("\n".join(lines), encoding="utf-8")
    print(OUT / "原三策略_支付宝规则重跑.md")


if __name__ == "__main__":
    main()
