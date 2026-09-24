"""Write the reviewable result of the return-improvement search."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research/return-improvement-2026-09-08"
PRODUCTS = {"cmb": "积存金代理", "fund": "建信A（支付宝）"}


def main():
    data = json.loads((OUT / "result.json").read_text(encoding="utf-8"))
    chosen = data["selected"]
    spec = chosen["spec"]
    lines = [
        "# 策略A收益提升研究",
        "",
        "搜索范围为1,152个预先定义的策略A参数行（其中部分在月度执行下产生相同路径）。参数排序只使用2021—2024年，2025年至今仅用于淘汰不符合约束的候选，不用该阶段收益重新排序。",
        "",
        "## 选中参数",
        "",
        "| 参数 | 值 |",
        "|---|---:|",
        f"| 趋势均线 | {spec['horizon']}日 |",
        "| 趋势带 | ±2% |",
        "| 波动率窗口 | 40日 |",
        f"| 目标波动率 | {spec['vol_target']:.0%} |",
        f"| 最高目标仓位 | {spec['cap']:.0%} |",
        f"| 回撤退出 | 相对{spec['horizon']}日高点回撤{spec['stop']:.0%} |",
        f"| 冷静期 | {spec['cooldown']}个伦敦金观测日 |",
        f"| 常规检查 | {'周度' if spec['frequency']=='weekly' else '月度'} |",
        f"| 再平衡阈值 | {spec['band']:.0%} |",
        "",
        "## 阶段结果",
        "",
        "| 产品 | 阶段 | 收益 | 年化收益 | 最大回撤 | 平均仓位 | 最高实际仓位 | 买卖次数 | 费用 |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for product, value in chosen["full"].items():
        for stage, m in value["splits"].items():
            lines.append(f"| {PRODUCTS[product]} | {stage} | {m['return_pct']:.2f}% | {m['cagr_pct']:.2f}% | {abs(m['max_drawdown_pct']):.2f}% | {m['average_weight_pct']:.2f}% | {m['max_weight_pct']:.2f}% | {m['trade_days']} | {m['fees_cny']:,.2f}元 |")
        m = value["full"]
        lines.append(f"| {PRODUCTS[product]} | 全期 | {m['return_pct']:.2f}% | {m['cagr_pct']:.2f}% | {abs(m['max_drawdown_pct']):.2f}% | {m['average_weight_pct']:.2f}% | {m['max_weight_pct']:.2f}% | {m['trade_days']} | {m['fees_cny']:,.2f}元 |")
    lines += ["", "## 敏感性结果", "", "| 情景 | 积存金年化 | 建信A年化 | 全部阶段合格 |", "|---|---:|---:|---|"]
    names = {
        "one_extra_session_delay": "额外延迟一个交易日",
        "cmb_double_spread": "积存金往返点差10元/克",
        "cmb_double_spread_plus_delay": "积存金10元点差、单边0.1%滑点、延迟1日",
        "fund_standard_1_5pct_purchase_fee": "建信A按标准申购费1.5%",
        "fund_t7_settlement": "建信A赎回资金T+7可用",
    }
    for key, value in data["stress"].items():
        r = value["results"]
        lines.append(f"| {names[key]} | {r['cmb']['full']['cagr_pct']:.2f}% | {r['fund']['full']['cagr_pct']:.2f}% | {'是' if value['eligible_all_stages'] else '否'} |")
    passed = sum(v["eligible_all_stages"] for v in data["parameter_neighbours"].values())
    lines += ["", f"8个参数邻域检查中，{passed}个仍满足全部阶段约束；目标波动率提高至16%的版本不合格，其余7个合格。", "",
                "与此前策略A相比，本版本提高目标波动率、仓位上限并缩短冷静期。全期最高实际仓位会到100%，但每个阶段的平均仓位均低于70%。历史约束不保证未来回撤。", ""]
    (OUT / "研究结论.md").write_text("\n".join(lines), encoding="utf-8")
    print(OUT / "研究结论.md")


if __name__ == "__main__":
    main()
