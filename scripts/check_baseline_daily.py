"""Fetch dated source snapshots and run one pre-specified execution stress."""
import sys
import json
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import asdict
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
from collect_market_data import get
from baseline_1_engine import Rules, simulate, metrics, hysteresis
from run_baseline_1 import BASE, overlay_signal
import plot_baseline_1_recent as charts

ROOT = Path(__file__).resolve().parents[1]
asof = sys.argv[1] if len(sys.argv)>1 else datetime.now().date().isoformat()
stress_name = sys.argv[2] if len(sys.argv)>2 else 'delay2_double_spread'
stress_cases = {
    'delay5_settlement7': (Rules(delay=5,settle_days=7), '信号执行额外延迟五个产品交易日，基金赎回到账延至T+7，费用不变。此为长假及操作延误的极端压力情景，不代替实际节假日日历。'),
    'delay1_costs2_settlement3': (Rules(delay=1,buy_fee=.003,cmb_halfspread=5,settle_days=3), '额外延迟一个产品交易日，基金申购费从0.15%升至0.30%、赎回到账延至T+3；积存金单边点差从2.5元扩大至5元。组合压力情景不作为实际平台费率声明。'),
    'delay2_double_spread': (Rules(delay=2,cmb_halfspread=5), '额外延迟两个产品交易日，积存金单边点差由2.5元扩大至5元；基金费用及到账不变。'),
    'fund_confirmation2_settlement3': (Rules(confirmation_delay=2,settle_days=3), '基金确认从T+1延至T+2，赎回到账从T+1延至T+3；确认后再一交易日才可赎回，其余费用及信号不变。积存金作为不受影响的对照。'),
}
stress_rules, stress_description = stress_cases[stress_name]
out = ROOT/'research/baseline-1'/('update-'+asof)
out.mkdir(exist_ok=True)
end = int(pd.Timestamp(asof, tz='UTC').timestamp())
urls = {
    'gold': f'https://www.westmetall.com/en/markdaten.php?action=table&field=USD_ozt_London&year={asof[:4]}',
    'fund': 'https://api.fund.eastmoney.com/f10/lsjz?fundCode=009033&pageIndex=1&pageSize=100',
    'fx': f'https://query1.finance.yahoo.com/v8/finance/chart/CNY%3DX?period1=1788739200&period2={end}&interval=1d&events=history',
}
def fetch(key):
    payload = get(urls[key], {'Referer':'https://fundf10.eastmoney.com/'} if key=='fund' else None)
    (out/(key+'.raw')).write_bytes(payload)
    return {'source':key,'url':urls[key],'bytes':len(payload),'fetched_at':datetime.now(timezone.utc).isoformat()}
with ThreadPoolExecutor(max_workers=3) as pool:
    sources = list(pool.map(fetch, urls))
(out/'sources.json').write_text(json.dumps(sources,indent=2),encoding='utf-8')
sys.argv = ['plot_baseline_1_recent.py','--asof',asof]
gold, frame, signal, summary = charts.main()
cutoff = summary['cutoff']
phases = [('2021—2023','2021-01-04','2023-12-31'),('2024','2024-01-01','2024-12-31'),('2025至今','2025-01-01',cutoff)]
# A single fixed stress, not parameter search: two extra product sessions,
# twice the original CMB spread, unchanged fund fees and settlement.
cases = {'baseline':Rules(),stress_name:stress_rules}
results={}
for name,rules in cases.items():
    results[name]={'rules':asdict(rules),'products':{}}
    for product in ['fund','cmb']:
        detail,_,_=simulate(frame,signal,product,BASE,rules)
        phase_results={label:metrics(detail,a,b) for label,a,b in phases}
        results[name]['products'][product]={
            'full':metrics(detail,'2021-01-04',cutoff),'phases':phase_results,
            'passes':all(m['max_drawdown_pct']>-15 and m['average_weight_pct']<=70 for m in phase_results.values())}
(out/'execution_stress.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
latest={'checked_at':datetime.now().astimezone().isoformat(),'strategy':'基准1',
        'signal_date':str(gold.index[-1].date()),'gold_am_usd_oz':float(gold.iloc[-1]),
        'source':urls['gold'],'target_weight':summary['target_weight'],
        'trend_state':float(hysteresis(gold,120).iloc[-1]),'ma120':float(gold.rolling(120).mean().iloc[-1]),
        'notes':['Signal uses observations strictly before today. No account balance or orders accessed.',
                 'Fund execution requires the next eligible Chinese dealing day; no same-day London fix execution.'],
        'report':str(out.relative_to(ROOT)/'summary.json')}
(ROOT/'research/baseline-1/latest_signal.json').write_text(json.dumps(latest,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({n:{p:{'full':r['full'],'passes':r['passes']} for p,r in c['products'].items()} for n,c in results.items()},ensure_ascii=False))
