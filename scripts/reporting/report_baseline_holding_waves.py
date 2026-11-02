"""Group actual simulated exposure into flat-to-flat holding episodes."""
import json
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
latest=json.loads((ROOT/'research/baseline-1/latest_signal.json').read_text(encoding='utf-8'))
source=(ROOT/latest['report']).parent
result={'source':str(source),'definition':'Actual positive holdings until actual holdings return to zero; net equity change includes costs and pending redemption receivables. Return denominator is total portfolio equity before first buy, not cumulative purchases.','products':{}}
for product in ['fund','cmb']:
    daily=pd.read_json(source/(product+'_daily.json'),orient='table')
    rows=[]
    opened=None
    previous=float(daily.equity.iloc[0])
    for date,row in daily.iterrows():
        if opened is None and row.weight>1e-10:
            opened={'buy_date':str(date.date()),'starting_equity':previous}
        if opened is not None and row.weight<=1e-10:
            start=opened['buy_date']
            part=daily.loc[start:date]
            pnl=float(row.equity)-opened['starting_equity']
            rows.append({**opened,'sell_date':str(date.date()),'ending_equity':float(row.equity),
                         'net_pnl':pnl,'return_pct':pnl/opened['starting_equity']*100,
                         'cost':float(part.fee.sum()),'trade_days':int(part.traded.sum()),
                         'calendar_days':(date-pd.Timestamp(start)).days})
            opened=None
        previous=float(row.equity)
    assert opened is None, 'Open episode requires unrealized P&L handling'
    assert abs(sum(x['net_pnl'] for x in rows)-(daily.equity.iloc[-1]-daily.equity.iloc[0]))<1e-5
    assert abs(sum(x['cost'] for x in rows)-daily.fee.sum())<1e-5
    result['products'][product]=rows
out=source/'holding_waves.json'
out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
for product,rows in result['products'].items():
    print(product)
    for i,r in enumerate(rows,1):
        print(f"{i} | {r['buy_date']} | {r['sell_date']} | {r['calendar_days']} | {r['net_pnl']:.2f} | {r['return_pct']:.2f}% | {r['cost']:.2f}")
