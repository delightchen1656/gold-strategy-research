"""Extend frozen baseline using downloaded snapshots, then plot a trailing window.

Raw snapshots are preserved in the dated output folder. This script does not
change baseline parameters, frozen input history, or account positions.
"""
import argparse
import io
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd

from baseline_1_engine import load_inputs, simulate, metrics, INITIAL
from run_baseline_1 import BASE, overlay_signal

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--asof', default='2026-09-28')
    args = parser.parse_args()
    asof = pd.Timestamp(args.asof)
    start = asof - pd.DateOffset(years=5)
    out = ROOT / 'research/baseline-1' / ('update-' + args.asof)
    gold, frozen = load_inputs()
    frozen_cutoff = frozen.index[-1]
    table = pd.read_html(io.StringIO((out / 'gold.raw').read_text(encoding='utf-8')))[0]
    table.columns = ['date', 'price']
    table['date'] = pd.to_datetime(table.date, format='%d. %B %Y', errors='coerce')
    table['price'] = pd.to_numeric(table.price.astype(str).str.replace(',', ''), errors='coerce')
    extra = table.dropna().set_index('date').price.sort_index()
    extra = extra[(extra.index > gold.index[-1]) & (extra.index < asof)]
    gold = pd.concat([gold, extra])
    assert gold.index.is_unique and gold.index.is_monotonic_increasing
    assert gold.pct_change().loc[extra.index].abs().max() < .2

    raw_fund = json.loads((out / 'fund.raw').read_bytes())['Data']['LSJZList']
    fund = pd.DataFrame([{'date': x['FSRQ'], 'nav': float(x['DWJZ']),
                         'acc_nav': float(x['LJJZ']),
                         'fund_buy': x['SGZT'] == '开放申购',
                         'fund_sell': x['SHZT'] == '开放赎回'} for x in raw_fund])
    fund['date'] = pd.to_datetime(fund.date)
    fund = fund.set_index('date').sort_index()
    overlap = fund.index.intersection(frozen.index)
    assert len(overlap) > 0
    assert np.allclose(fund.loc[overlap, 'nav'], frozen.loc[overlap, 'nav'])
    fund = fund.loc[(fund.index > frozen_cutoff) & (fund.index < asof)]
    assert len(fund) > 0 and np.allclose(fund.nav, fund.acc_nav), 'Corporate action review needed'

    fxraw = json.loads((out / 'fx.raw').read_bytes())['chart']['result'][0]
    stamps = pd.to_datetime(fxraw['timestamp'], unit='s', utc=True)
    dates = stamps.tz_convert(fxraw['meta']['exchangeTimezoneName']).tz_localize(None).normalize()
    fx = pd.Series(fxraw['indicators']['quote'][0]['close'], index=dates).dropna()
    cutoff = min(fund.index.max(), gold.index.max(), fx.index.max(), asof-pd.Timedelta(days=1))
    fund = fund.loc[:cutoff].copy()
    assert fund.index.isin(gold.index).all(), 'Missing gold valuation dates'
    assert fund.index.isin(fx.index).all(), 'Missing FX valuation dates'
    fund['cmb_mid'] = gold.reindex(fund.index) * fx.reindex(fund.index) / 31.1034768
    fund['cmb_trade'] = fund.fund_buy & fund.index.isin(gold.index)
    frame = pd.concat([frozen, fund])
    assert frame.index.is_unique
    signals = overlay_signal(gold, frame.index)
    old = json.loads((ROOT / 'research/baseline-1/result.json').read_text(encoding='utf-8'))
    results, daily = {}, {}
    for product in ['fund', 'cmb']:
        det, trades, _ = simulate(frame, signals, product, BASE, detail=True)
        # Historical replay must remain identical before extending the window.
        prior = metrics(det, end=str(frozen_cutoff.date()))
        assert abs(prior['return_pct'] - old['selected'][product]['full']['return_pct']) < 1e-7
        results[product] = metrics(det, start=str(start.date()), end=str(cutoff.date()))
        results[product]['latest_actual_weight_pct'] = float(det.weight.iloc[-1]*100)
        daily[product] = det
        det.to_json(out / (product+'_daily.json'), orient='table', date_format='iso', indent=2)
        (out / (product+'_trades.json')).write_text(json.dumps(trades, ensure_ascii=False, indent=2), encoding='utf-8')
    # Signals for today's submission use observations strictly before today.
    target = float(overlay_signal(gold, pd.DatetimeIndex([asof]))[0])
    report = {'window_start': str(start.date()), 'cutoff': str(cutoff.date()),
              'latest_signal_date': str(gold.index[-1].date()), 'target_weight': target,
              'results': results, 'historical_replay_matches': True,
              'notes': ['Frozen history retained; later observations appended.',
                        'Actual simulated holdings, not user account holdings.',
                        'CMB price proxy uses model halfspread of CNY 2.5 per gram.',
                        'No fabricated NAVs beyond source cutoff.']}
    (out / 'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei']
    plt.rcParams['axes.unicode_minus'] = False
    labels = {'fund': '建信A', 'cmb': '积存金代理'}
    colors = {'fund': '#be8418', 'cmb': '#2765a0'}
    for kind in ['returns', 'positions']:
        fig, ax = plt.subplots(figsize=(13, 5.5), facecolor='#fafbfd')
        ax.set_facecolor('#fafbfd')
        for product, det in daily.items():
            selected = det.loc[start:cutoff]
            base = float(det.loc[det.index < start].equity.iloc[-1])
            y = (selected.equity/base-1)*100 if kind == 'returns' else selected.weight*100
            ax.plot(selected.index, y, label=labels[product], color=colors[product],
                    lw=1.7, linestyle='-' if product == 'fund' else '--', alpha=.9)
            if kind == 'returns':
                ax.annotate(f'{y.iloc[-1]:.2f}%', (selected.index[-1], y.iloc[-1]),
                            xytext=(7,0), textcoords='offset points', color=colors[product], fontsize=11)
        if kind == 'positions':
            ax.step(frame.loc[start:cutoff].index, signals[frame.index >= start]*100,
                    where='post', color='#75808b', lw=.8, alpha=.55, label='目标仓位')
            ax.set_ylim(-3, 105)
            ax.set_yticks(range(0, 101, 20))
        title = '近5年累计收益' if kind == 'returns' else '近5年仓位变化'
        ax.set_title('基准1｜'+title, loc='left', fontsize=20, pad=20)
        ax.set_ylabel('累计收益（%）' if kind == 'returns' else '黄金市值 / 组合资产（%）')
        ax.xaxis.set_major_locator(mdates.YearLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
        ax.set_xlim(start, cutoff+pd.Timedelta(days=95))
        ax.grid(alpha=.17)
        ax.spines[['top', 'right']].set_visible(False)
        ax.legend(loc='upper left', frameon=False, ncol=3)
        fig.text(.07,.058,f'{start:%Y-%m-%d} 至 {cutoff:%Y-%m-%d}｜继承原策略历史持仓｜含模型交易成本｜非个人账户实盘',fontsize=10,color='#596571')
        note = '区间收益以窗口前一交易日资产为基数；积存金为人民币价格代理。' if kind == 'returns' else f'按基金净值日展示；最新信号 {gold.index[-1]:%Y-%m-%d}，目标仓位 {target:.0%}。'
        fig.text(.07,.02,note,fontsize=10,color='#596571')
        fig.tight_layout(rect=[0,.1,1,1])
        fig.savefig(out / (kind+'.png'), dpi=170)
        plt.close(fig)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return gold, frame, signals, report


if __name__ == '__main__':
    main()
