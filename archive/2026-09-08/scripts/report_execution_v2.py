"""Create the concise research report and typed workbook input from frozen results."""
import json
from pathlib import Path
from research_execution_v2 import OUT, INITIAL, SPLITS

NAMES={"vol_trend":"趋势＋波动率控仓＋回撤退出","dual_momentum":"双周期动量＋波动率控仓",
       "pullback":"趋势内回调买入","trend_trail":"趋势＋回撤退出","ensemble":"多周期趋势组合",
       "channel":"快退出通道","legacy_channel":"旧策略1：通道突破","legacy_momentum":"旧策略2：波动率动量",
       "legacy_macro":"旧策略3：宏观状态","hold":"买入持有"}
PRODUCTS={"cmb":"积存金代理","fund":"建信A"}


def main():
    r=json.loads((OUT/"result.json").read_text(encoding="utf-8"))
    c=next(x for x in r["candidates"] if x["id"]==r["primary_id"])
    name=NAMES[c["spec"]["family"]]
    lines=["# 黄金策略研究复核与替换", "", f"研究日期：2026-09-07。共同回测区间：{r['start']}至{r['end']}。每个产品初始5万元、全现金开始、无追加资金。", "",
           f"当前主候选：**{name}**。六类方法、288个登记版本先仅使用2021—2024年选参；各类冠军固定后检查2025年以来约束。主候选按前期排名选取，不按后段收益重新排序。", "",
           "基金结果采用支付宝截图确认的0.15%申购费与赎回T+1余额宝到账。积存金缺少历史客户成交价，采用公开中间价与5元/克往返点差，属于代理回测。", "",
           "## 阶段收益", "", "| 产品 | 阶段 | 累计收益 | 最大回撤 | 平均仓位 |", "|---|---|---:|---:|---:|"]
    workbook_rows=[]
    for path,values in c["results"].items():
        base=INITIAL
        for label,_,_ in SPLITS:
            m=values["splits"][label]
            lines.append(f"| {PRODUCTS[path]} | {label} | {m['return_pct']:.2f}% | {abs(m['max_drawdown_pct']):.2f}% | {m['average_weight_pct']:.2f}% |")
            workbook_rows.append(dict(product=PRODUCTS[path],period=label,initial=base,**m))
            base=m["final_cny"]
    lines += ["", "| 产品 | 全期累计收益 | 年化收益 | 全期最大回撤 | 期末资产 | 买卖合计次数 |", "|---|---:|---:|---:|---:|---:|"]
    for path,values in c["results"].items():
        m=values["full"]
        lines.append(f"| {PRODUCTS[path]} | {m['return_pct']:.2f}% | {m['cagr_pct']:.2f}% | {abs(m['max_drawdown_pct']):.2f}% | {m['final_cny']:,.2f}元 | {m['trade_days']} |")
        workbook_rows.append(dict(product=PRODUCTS[path],period="全期",initial=INITIAL,**m))
    lines += ["", "## 逐年收益", "", "| 年份 | 积存金代理 | 建信A |", "|---|---:|---:|"]
    for year in map(str,range(2021,2027)):
        lines.append(f"| {year if year!='2026' else '2026至9月4日'} | {c['results']['cmb']['years'][year]['return_pct']:.2f}% | {c['results']['fund']['years'][year]['return_pct']:.2f}% |")
    for path,values in c["results"].items():
        base=INITIAL
        for year,m in values["years"].items():
            workbook_rows.append(dict(product=PRODUCTS[path],period=year if year!="2026" else "2026至9月4日",initial=base,**m))
            base=m["final_cny"]
    lines += ["", "## 同口径比较", "", "旧策略已用新账本、共同截止日和相同成本复算。旧策略保留月末信号，宏观数据保守延迟一个源观测日；原始文件中的旧收益不直接用于排名。", "",
              "| 方法 | 积存金年化 | 建信A年化 | 最差产品全期回撤 | 六个阶段均合格 |", "|---|---:|---:|---:|---|"]
    comparisons=[]
    for x in [c]+r["baselines"]+ [x for x in r["candidates"] if x["id"]!=c["id"]]:
        label=NAMES[x["spec"]["family"]]
        if x["spec"]["family"]=="hold": label=f"初始{round(x['spec']['cap']*100)}%买入后持有"
        a=x["results"]["cmb"]["full"]; b=x["results"]["fund"]["full"]
        dd=-min(a["max_drawdown_pct"],b["max_drawdown_pct"])
        lines.append(f"| {label} | {a['cagr_pct']:.2f}% | {b['cagr_pct']:.2f}% | {dd:.2f}% | {'是' if x['eligible_all_stages'] else '否'} |")
        comparisons.append([label,a["cagr_pct"]/100,b["cagr_pct"]/100,dd/100,"是" if x["eligible_all_stages"] else "否"])
    lines += ["", "合格旧动量策略保留为对照。低收益的新方法不因通过约束就自动替换旧策略。当前主研究方向更新为上述主候选。", "",
              "## 成本与执行敏感性", "", "| 情景 | 积存金年化 | 建信A年化 | 六个阶段均合格 |", "|---|---:|---:|---|"]
    stress_names={"fund_standard_fee":"基金申购标准费率1.5%","fund_t7_settlement":"基金赎回T+7到账",
                  "extra_one_session_delay":"增加一个产品交易日延迟",
                  "cmb_double_spread":"积存金往返点差10元/克","combined_cost_delay":"延迟1日＋积存金10元点差及单边0.1%滑点",
                  "fund_bank_card_t3":"基金赎回到银行卡T+3到账"}
    for k,v in c["stress"].items():
        lines.append(f"| {stress_names[k]} | {v['results']['cmb']['full']['cagr_pct']:.2f}% | {v['results']['fund']['full']['cagr_pct']:.2f}% | {'是' if v['eligible_all_stages'] else '否'} |")
    neighbors=r["primary_parameter_sensitivity"]
    lines += ["",f"主候选的8个单参数扰动情景中，{sum(x['eligible_all_stages'] for x in neighbors)}个仍满足全部阶段约束；仅作敏感性检查，没有据此更换已选参数。", "",
              "## 简要规则", "",
              "120日趋势带2%上下滞回；40日历史波动率决定仓位，目标波动率12%，最高目标仓位85%，目标按5个百分点取整。常规目标在每月首个伦敦观测日收盘后检查。相对120日高点回落超过12%时每日触发退出，退出后至少等待10个伦敦观测日且风险解除，再等下次常规检查恢复。实际仓位偏离目标10个百分点才再平衡；价格上涨造成的自然仓位漂移完整保留。", "",
              "## 执行口径与复核", "",
              "- 收盘后计算信号，下一可交易日执行。基金买入金额、卖出份额按执行前已知资产与净值确定，不使用未知的成交日净值反推订单。",
              "- 实际现金、份额和FIFO批次核算；买入T+1确认，保守按T+2可赎回。按买入与赎回确认日期之差计持有天数：不足7日1.5%，7日至不足30日0.5%，满30日0%。没有为了免手续费强行锁仓。",
              "- 基金按支付宝规则以T+1确认，赎回款T+1进入余额宝可用；期间列为应收款，不能复用。份额取到0.01份，金额到分，舍入差额回到现金。净值已包含运作费用，不重复扣管理费。",
              "- 积存金按最新点差结构的固定情景测算，不声称重建历史点差。买卖各2.5元/克；最小买入取1000元与1克金额的较大值、最小常规卖出1克、克数0.0001精度是保守建模假设，未核实完整历史下单规则。",
              "- 两产品以基金净值日期作为共同估值日。积存金仅在有伦敦观测且中国产品可交易时下单，可能漏掉实际可交易时段；汇率与伦敦定价并非同一时刻的可成交组合报价。",
              "- 平均仓位按阶段内每日可得净值时点的持仓市值/总资产算术平均，包含应收款和现金；最大回撤为每日估值回撤。另报告全期回撤，避免阶段划分掩盖跨段损失。",
              "- 分段收益使用上一阶段最后净资产作为基数，保留阶段首日收益与成本；三个阶段复利与全期一致。期末以净值/中间价估值，未假设期末清仓。",
              "- 七项检查覆盖份额漂移、申购费用、FIFO费率边界、到账前不能复用资金、未知净值订单、逐笔与每日资产对账、未来数据截断不改变此前信号。",
              "- 旧研究已经使用过2025年以来的数据；这次虽只在2021—2024年选参，后段仍不是真正从未接触的盲测。历史限制不是未来回撤保证。", "",
              "## 数据与公开规则来源", "",
              "- [基金管理人资料概要](https://www.ccbfund.cn/u/cms/jx/brief/009033.pdf)：公开文件编制于2024年，标准申购及赎回费。已保存源文件。",
              "- [基金开放申赎公告](https://static.cninfo.com.cn/finalpage/2020-08-12/1208154684.PDF)：009033代码、申请与数量限制、费用。",
              "- [基金招募说明书（银行转载）](https://card.cgbchina.com.cn/noticeNewDetail.gsp?id=2515664&symbol=009033)：未知价、金额申购份额赎回、FIFO及T+7以内支付。",
              "- [招商银行产品说明](https://market.cmbchina.com/personal/gjsgcpqb/gjsgcpqb.htm)：黄金账户报价含点差，国内外黄金报价基础；页面较旧。",
              "- [2026年招行点差调整报道](https://finance.sina.com.cn/money/bank/gsdt/2026-03-24/doc-inhsarqw7542780.shtml)：3月23日往返点差5元、6月29日起双边各2.5元；历史逐笔报价仍缺失。",
              "- [伦敦金观测](https://www.westmetall.com/en/markdaten.php?action=table&field=USD_ozt_London&year=2026)：补齐9月1日至4日。2026-01-02明显异常报价不纳入，未编造补值；旧2022-07-20异常也继续排除。",
              "- Yahoo汇率重新下载并按元数据Europe/London日期保存，修复旧UTC日期在夏令时期间的错位；原文件未覆盖。基金沿用本地009033净值与开放状态，累计净值等于单位净值。输入哈希见data_audit.json。", "",
              "## 复现", "", "```powershell", "python scripts/research_execution_v2.py prepare", "python scripts/research_execution_v2.py select", "python scripts/research_execution_v2.py validate", "python scripts/test_research_execution_v2.py", "python scripts/report_execution_v2.py", "```", ""]
    (OUT/"研究结论.md").write_text("\n".join(lines),encoding="utf-8")
    ledger=json.loads((OUT/f"ledger_{c['id']}.json").read_text(encoding="utf-8"))
    trade_rows=[]
    for p,v in ledger.items():
        for t in v["trades"]:
            trade_rows.append([PRODUCTS[p],t["date"],"买入" if t["side"]=="buy" else "卖出",t["units"],t["price"],t["cash_amount"],t["fee"],t["target"]])
    trade_rows.sort(key=lambda x:(x[1],x[0]))
    (OUT/"workbook_data.json").write_text(json.dumps({"name":name,"rows":workbook_rows,"comparisons":comparisons,"trades":trade_rows},ensure_ascii=False,indent=2),encoding="utf-8")
    print(OUT/"研究结论.md")


if __name__=="__main__": main()
