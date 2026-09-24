"""Render the current three selected strategies for both supported products."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research/execution-v2-2026-09-07"
NAMES = {
    "vol_trend": "策略A：趋势＋波动率控仓＋回撤退出",
    "dual_momentum": "策略B：双周期动量＋波动率控仓",
    "pullback": "策略C：趋势内回调买入",
}
PRODUCTS = {"cmb": "积存金代理", "fund": "建信A（支付宝）"}


def main():
    report = json.loads((OUT / "result.json").read_text(encoding="utf-8"))
    selected = [next(item for item in report["candidates"] if item["id"] == item_id)
                for item_id in report["selected_ids"]]
    lines = [
        "# 最新三策略：建信A与积存金重跑",
        "",
        "统一口径：2021-01-04至2026-09-04；每个产品独立初始5万元；建信A按支付宝申购费0.15%、T日净值、T+1确认、确认后下一交易日可卖、赎回后T+1余额宝可用；积存金使用公开中间价代理和买卖各2.5元/克点差。",
        "",
        "## 全期结果",
        "",
        "| 策略 | 产品 | 全期收益 | 年化收益 | 最大回撤 | 平均仓位 | 最高实际仓位 | 期末资产 | 买卖次数 | 费用 | 三阶段均合格 |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for item in selected:
        name = NAMES[item["spec"]["family"]]
        for path, value in item["results"].items():
            m = value["full"]
            lines.append(
                f"| {name} | {PRODUCTS[path]} | {m['return_pct']:.2f}% | {m['cagr_pct']:.2f}% | "
                f"{abs(m['max_drawdown_pct']):.2f}% | {m['average_weight_pct']:.2f}% | {m['max_weight_pct']:.2f}% | "
                f"{m['final_cny']:,.2f}元 | {m['trade_days']} | {m['fees_cny']:,.2f}元 | "
                f"{'是' if item['eligible_all_stages'] else '否'} |"
            )
    lines += ["", "## 阶段结果", "", "| 策略 | 产品 | 阶段 | 收益 | 最大回撤 | 平均仓位 | 买卖次数 | 费用 |", "|---|---|---|---:|---:|---:|---:|---:|"]
    for item in selected:
        name = NAMES[item["spec"]["family"]]
        for path, value in item["results"].items():
            for stage, m in value["splits"].items():
                lines.append(
                    f"| {name} | {PRODUCTS[path]} | {stage} | {m['return_pct']:.2f}% | "
                    f"{abs(m['max_drawdown_pct']):.2f}% | {m['average_weight_pct']:.2f}% | "
                    f"{m['trade_days']} | {m['fees_cny']:,.2f}元 |"
                )
    lines += ["", "## 参数", "", "| 策略 | 参数 |", "|---|---|"]
    for item in selected:
        s = item["spec"]
        family = s["family"]
        specifics = {
            "vol_trend": "120日趋势带±2%，40日波动率，目标波动率12%",
            "dual_momentum": "60日与120日动量，40日波动率，目标波动率12%",
            "pullback": "120日趋势带±2%；价格低于MA的103%时为满目标，否则半目标",
        }[family]
        lines.append(
            f"| {NAMES[family]} | {specifics}；最高目标{int(s['cap']*100)}%；"
            f"120日高点回撤{int(s['stop']*100)}%退出；冷静期{s['cooldown']}日；"
            f"{ '周度' if s['frequency']=='weekly' else '月度'}检查；目标仓位偏离10个百分点再平衡。 |"
        )
    lines += [""]
    (OUT / "最新三策略_支付宝规则重跑.md").write_text("\n".join(lines), encoding="utf-8")
    print(OUT / "最新三策略_支付宝规则重跑.md")


if __name__ == "__main__":
    main()
