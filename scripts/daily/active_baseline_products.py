"""Separate fund/CNY proxy execution for the active London-close signal."""
import json
import numpy as np
import pandas as pd
from scripts.data.collect_market_data import get
from scripts.core.baseline_1_engine import load_inputs, simulate, Rules, Spec
from scripts.core.baseline_signal import generate_baseline_signal

def calculate(root,out,asof,d,cfg):
    _,frame=load_inputs()
    cutoff=frame.index[-1]
    rows=[];page=1
    while True:
        url=f'https://api.fund.eastmoney.com/f10/lsjz?fundCode=009033&pageIndex={page}&pageSize=20'
        raw=get(url,{'Referer':'https://fundf10.eastmoney.com/'})
        (out/f'fund_page{page}.raw').write_bytes(raw)
        new=json.loads(raw)['Data']['LSJZList'];assert new
        rows.extend(new)
        if min(x['FSRQ'] for x in new)<=str(cutoff.date()):break
        page+=1;assert page<100
    fund=pd.DataFrame([dict(date=x['FSRQ'],nav=float(x['DWJZ']),acc_nav=float(x['LJJZ']),fund_buy=x['SGZT']=='开放申购',fund_sell=x['SHZT']=='开放赎回') for x in rows])
    fund.date=pd.to_datetime(fund.date);fund=fund.set_index('date').sort_index()
    assert fund.index.is_unique and np.allclose(fund.nav,fund.acc_nav)
    fund=fund[(fund.index>cutoff)&(fund.index<pd.Timestamp(asof))]
    frame=pd.concat([frame,fund]).loc['2021-01-04':]
    fx=pd.read_csv(root/'research/baseline-1/inputs/fx.csv',parse_dates=['date']).set_index('date').close
    end=int(pd.Timestamp(asof,tz='UTC').timestamp())
    url=f'https://query1.finance.yahoo.com/v8/finance/chart/CNY%3DX?period1=1788220800&period2={end}&interval=1d'
    raw=get(url);(out/'fx.raw').write_bytes(raw);j=json.loads(raw)['chart']['result'][0]
    local=pd.to_datetime(j['timestamp'],unit='s',utc=True).tz_convert(j['meta']['exchangeTimezoneName'])
    vals=pd.Series(j['indicators']['quote'][0]['close'],index=local.tz_localize(None).normalize())
    vals=vals[(local.hour==0)&(local.minute==0)&(local.second==0)].dropna()
    vals=vals[(vals.index>fx.index[-1])&(vals.index<pd.Timestamp(asof))]
    fx=pd.concat([fx,vals]);assert fx.index.is_unique
    limit=min(frame.index.max(),d.index.max(),fx.index.max())
    frame=frame.loc[:limit].copy()
    missing=frame.index[~frame.index.isin(fx.index)|~frame.index.isin(d.index)]
    assert len(frame)
    # Fund NAV remains observed. CMB carries last known valuation on source
    # holidays, explicitly marked below, and cannot trade on those dates.
    frame['cmb_mid']=d.close.reindex(frame.index,method='ffill')*fx.reindex(frame.index,method='ffill')/31.1034768
    frame['cmb_trade']=frame.fund_buy & frame.index.isin(d.index) & frame.index.isin(fx.index)
    extended=pd.concat([d,d.iloc[[-1]].set_axis([d.index[-1]+pd.Timedelta(days=1)])])
    next_signal=generate_baseline_signal(extended,cfg)
    dated=pd.Series(next_signal[1:],index=d.index)
    pos=d.index.searchsorted(frame.index,side='left')-1
    sig=np.array([dated.iloc[i] if i>=0 else 0. for i in pos])
    result={}
    for product in ['fund','cmb']:
        detail,trades,_=simulate(frame,sig,product,Spec('hold',band=.05),Rules(),detail=True)
        detail.to_json(out/(product+'_daily.json'),orient='table',date_format='iso')
        (out/(product+'_trades.json')).write_text(json.dumps(trades,ensure_ascii=False,indent=2),encoding='utf-8')
        result[product]={'valuation_date':str(detail.index[-1].date()),'simulated_actual_weight_pct':float(detail.weight.iloc[-1]*100)}
    return {'positions':result,'cmb_carried_valuation_no_trade_dates':[str(x.date()) for x in missing],
            'note':'Fund actual NAV/fees; CMB CNY spot valuation proxy with 2.5 CNY/g halfspread, not bank quotes. No personal accounts. Strict prior London session signal.'}
