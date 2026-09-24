"""Independent arithmetic, date, and availability audit of the saved research outputs."""
from pathlib import Path
import json
import re
import numpy as np
import pandas as pd

R = Path(__file__).resolve().parent
checks = {}

def panel(name):
    return pd.read_csv(R / name, parse_dates=['date']).set_index('date')

def pred(name):
    p = pd.read_csv(R / name)
    assert np.isfinite(p[['actual', 'forecast']]).all().all()
    assert (p.latest_training_label <= p.date).all()
    assert (p.label_end > p.date).all()
    keys = ['date', 'target', 'model'] + [c for c in ['clock', 'variant'] if c in p]
    assert not p.duplicated(keys).any()
    checks[name + '_prediction_rows'] = len(p)
    return p

j1, j2, j3 = [json.loads((R / f'round{i}_results.json').read_text(encoding='utf-8')) for i in [1, 2, 3]]
p1 = pred('round1_predictions.csv')
p2 = pred('round2_price_predictions.csv')
pf = pred('round2_fund_predictions.csv')
p3 = pred('round3_predictions.csv')
pm = pred('round3_monthly_predictions.csv')
d0 = panel('daily_primary_panel.csv')
daily = {'GLD_SLV': d0, **{k: panel(f'round3_daily_{k}.csv') for k in ['IAU_SIVR', 'GC_SI', '2026_extension']}}

# Explicitly enumerate future returns: omit the next complete trading day.
n_targets = 0
for name, d in daily.items():
    assert d.index.is_unique and d.index.is_monotonic_increasing
    assert (d[['gold', 'silver']] > 0).all().all()
    g, s = np.log(d.gold.to_numpy()), np.log(d.silver.to_numpy())
    q = g - s
    for h in [5, 20]:
        for i in range(len(d) - h - 1):
            future = np.diff(g[i + 1:i + h + 2])
            expected = np.log(np.sqrt(np.mean(future * future) * 252))
            assert abs(expected - d[f'future_vol{h}'].iloc[i]) < 1e-9
            assert abs(g[i + h + 1] - g[i + 1] - d[f'future_return{h}'].iloc[i]) < 1e-9
            assert abs(q[i + h + 1] - q[i + 1] - d[f'future_ratio{h}'].iloc[i]) < 1e-9
            assert pd.Timestamp(d[f'end{h}'].iloc[i]) == d.index[i + h + 1]
            n_targets += 3
    past = np.log(d.gold / d.silver).diff(5)
    for i in range(300, len(d), 113):
        hist = past.iloc[i - 252:i].to_numpy()
        expected = (past.iloc[i] - hist.mean()) / hist.std(ddof=1)
        assert abs(expected - d.qz.iloc[i]) < 1e-8
checks['daily_targets_recomputed'] = n_targets
checks['latest_new_price_date'] = str(daily['2026_extension'].index[-1].date())

# All target values in prediction files must agree with their underlying observations.
def daily_prediction_targets(p, d):
    for target, a in p.groupby('target'):
        dates = pd.to_datetime(a.date)
        assert np.allclose(a.actual, d.loc[dates, target], atol=1e-10)

daily_prediction_targets(p1, d0)
daily_prediction_targets(p2, d0)
for variant, a in p3.groupby('variant'):
    daily_prediction_targets(a, d0 if variant == 'rolling_5_years' else daily[variant])

w = panel('round2_cot_panel.csv')
for target, a in pf.groupby('target'):
    metal, side, hs = re.match(r'future_([gs])_(long|short|net)_(\d)w', target).groups()
    h = int(hs)
    value = (w[f'{metal}_{side}_contracts'].shift(-h) - w[f'{metal}_{side}_contracts']) / w[f'{metal}_oi']
    dates = pd.to_datetime(a.date)
    assert np.allclose(a.actual, value.loc[dates], atol=1e-10)
    expected_end = pd.Series(w.index, index=w.index).shift(-h)
    assert np.array_equal(pd.to_datetime(a.label_end).to_numpy(), expected_end.loc[dates].to_numpy())

m = panel('round3_monthly_panel.csv')
for target, a in pm.groupby('target'):
    kind, hs = re.match(r'(gold|ratio)_return_(\d+)m', target).groups()
    h = int(hs)
    value = np.log(m.gold if kind == 'gold' else m.gold / m.silver)
    truth = value.shift(-h - 1) - value.shift(-1)
    dates = pd.to_datetime(a.date)
    assert np.allclose(a.actual, truth.loc[dates], atol=1e-10)
    expected_end = pd.Series(m.index, index=m.index).shift(-h - 1)
    assert np.array_equal(pd.to_datetime(a.label_end).to_numpy(), expected_end.loc[dates].to_numpy())
checks['all_prediction_actuals_and_labels'] = 'PASS'

# Verify each published error change directly from saved prediction residuals.
n_mse = 0
def audit_mse(result, p, monthly=False):
    global n_mse
    a = p[p.target == result['target']]
    bounds = {'all': ('1900', '2099'), 'early': ('1900', '2018-12-31'),
              'recent': ('2019', '2025-12-31'), '2026': ('2026', '2026-12-31')}
    if monthly:
        bounds.update(early=('2000', '2012-12-31'), recent=('2013', '2025-12-31'))
    start, end = bounds[result['period']]
    a = a[(a.date >= start) & (a.date <= end)]
    wide = a.pivot(index='date', columns='model', values='forecast')
    actual = a.groupby('date').actual.first()
    base, model = result.get('baseline', 'base'), result['model']
    err0 = np.mean((wide[base] - actual) ** 2)
    err1 = np.mean((wide[model] - actual) ** 2)
    assert len(wide) == result['n']
    assert wide.index[0] == result['first'] and wide.index[-1] == result['last']
    assert abs(err0 - result['base_mse']) < 1e-9
    assert abs(err1 - result['extended_mse']) < 1e-9
    assert abs(100 * (err1 / err0 - 1) - result['mse_change_pct']) < 1e-8
    n_mse += 1

for r in j1['results']: audit_mse(r, p1)
for r in j2['price_results']: audit_mse(r, p2[p2.clock == r['clock']])
for r in j2['fund_results']: audit_mse(r, pf)
for r in j3['robustness']:
    v = r['variant']
    if v.startswith('GLD_SLV_matched_'):
        alt = v.removeprefix('GLD_SLV_matched_')
        dates = p3[(p3.variant == alt) & (p3.target == 'future_vol20')].date.unique()
        a = p1[p1.date.isin(dates)]
    elif v == 'exclude_pandemic_overlap':
        a = p1[~((p1.date <= '2020-06-30') & (p1.label_end >= '2020-02-15'))]
    else: a = p3[p3.variant == v]
    audit_mse(r, a)
for r in j3['monthly_results']: audit_mse(r, pm, monthly=True)
checks['error_comparisons_recomputed'] = n_mse

# Check holdings totals, observed public-data ages, and all declared blackout windows.
raw = pd.DataFrame(json.loads((R / 'sources/cot_full_2025.json').read_text()))
names = ['open_interest_all', 'tot_rept_positions_long_all', 'nonrept_positions_long_all',
         'tot_rept_positions_short', 'nonrept_positions_short_all']
raw[names] = raw[names].apply(pd.to_numeric)
assert (raw[names[1]] + raw[names[2]] == raw[names[0]]).all()
assert (raw[names[3]] + raw[names[4]] == raw[names[0]]).all()
for clock, minimum in [('position_date', 0), ('delayed_10_days', 10)]:
    a = panel(f'round2_price_panel_{clock}.csv')
    age = (a.index - pd.to_datetime(a.cot_asof)).dt.days
    valid = a.g_mm_net.notna()
    assert age[valid].between(minimum, 24).all()
    for start, end in j2['excluded_observation_windows']:
        assert a.loc[start:end, 'g_mm_net'].isna().all()
checks['cot_balance_rows'] = len(raw)
checks['cot_availability_and_blackouts'] = 'PASS'

# Refit selected forecasts in unstandardized coordinates to check the independent result.
strong = ['gvol5', 'gvol20', 'gvol60', 'gret5', 'gret20', 'log_vix', 'dollar20', 'real20', 'sp20', 'log_gvz']
models = {'macro': strong[:-1], 'gvz': strong,
          'speed': strong + ['qret5', 'qret20'], 'acceleration': strong + ['qaccel'],
          'raw_shock': strong + ['qabs'], 'residual_shock': strong + ['surprise_abs'],
          'asymmetric_shock': strong + ['surprise_up', 'surprise_down']}
refits = 0
def audit_refit(p, a, mm, target, end, window=None):
    global refits
    union = list(dict.fromkeys(c for cols in mm.values() for c in cols))
    data = a[union + [target, end]].dropna().copy()
    data[end] = pd.to_datetime(data[end])
    choices = p[p.target == target].date.unique()
    for date in choices[np.unique([0, len(choices) // 2, len(choices) - 1])]:
        dt = pd.Timestamp(date)
        train = data[(data.index < dt) & (data[end] <= dt)]
        if window: train = train.loc[dt - pd.DateOffset(years=window):]
        for model, cols in mm.items():
            saved = p[(p.target == target) & (p.date == date) & (p.model == model)].iloc[0]
            x = np.column_stack([np.ones(len(train)), train[cols]])
            coeff = np.linalg.lstsq(x, train[target].to_numpy(), rcond=None)[0]
            prediction = np.r_[1., data.loc[dt, cols].to_numpy()] @ coeff
            assert len(train) == saved.training_n
            assert abs(prediction - saved.forecast) < 1e-8
            refits += 1

week = panel('round1_weekly_panel.csv')
for target, h in [('future_vol5', 5), ('future_vol20', 20), ('future_return20', 20)]:
    audit_refit(p1, week, models, target, f'end{h}')
    audit_refit(p3[p3.variant == 'rolling_5_years'], week, models, target, f'end{h}', window=5)
    for variant in ['IAU_SIVR', 'GC_SI', '2026_extension']:
        source = daily[variant]
        selected = source.groupby(source.index.to_period('W-FRI')).tail(1)
        selected = selected[selected.index.to_period('W-FRI').end_time.normalize() <= source.index.max()]
        audit_refit(p3[p3.variant == variant], selected, models, target, f'end{h}')
for clock in ['position_date', 'delayed_10_days']:
    a = panel(f'round2_price_panel_{clock}.csv')
    b = strong + ['qret5', 'qret20']
    mm = {'base': b,
          'net_positions': b + ['g_mm_net', 's_mm_net', 'g_mm_net_delta', 's_mm_net_delta'],
          'long_short_components': b + ['g_mm_net', 's_mm_net', 'g_long_delta', 'g_short_delta', 's_long_delta', 's_short_delta'],
          'extreme_positions': b + ['g_tail', 's_tail']}
    for h in [5, 20]:
        for target in [f'future_return{h}', f'future_ratio{h}']:
            audit_refit(p2[p2.clock == clock], a, mm, target, f'end{h}')
for target in pm.target.unique():
    kind, hs = re.match(r'(gold|ratio)_return_(\d+)m', target).groups()
    b = ['g1', 'g12'] if kind == 'gold' else ['q1', 'q12']
    mm = {'base': b, 'rolling_level': b + ['q_z120'], 'nonlinear_tails': b + ['q_high', 'q_low']}
    m['audit_end'] = pd.Series(m.index, index=m.index).shift(-int(hs) - 1)
    audit_refit(pm, m, mm, target, 'audit_end')
for target in pf.target.unique():
    metal, side, hs = re.match(r'future_([gs])_(long|short|net)_(\d)w', target).groups()
    lev = metal + '_mm_net' if side == 'net' else f'{metal}_{side}_level'
    b = [f'{metal}_{side}_lag{k}' for k in range(4)] + [lev, 'gret1', 'gret4', 'log_vix', 'log_gvz', 'dollar20', 'real20']
    mm = {'base': b, 'ratio_speed': b + ['qret1', 'qret4'], 'ratio_level': b + ['qlevel_z']}
    w['audit_end'] = pd.Series(w.index, index=w.index).shift(-int(hs))
    audit_refit(pf, w, mm, target, 'audit_end')
checks['independent_forecast_refits'] = refits

# Newly downloaded 2026 data must not replace historical explanatory variables.
old_features = list(dict.fromkeys(c for cols in models.values() for c in cols))
ext = daily['2026_extension']
ix = d0.index.intersection(ext.index)
assert np.allclose(d0.loc[ix, old_features], ext.loc[ix, old_features], equal_nan=True, atol=1e-8)
checks['extension_preserves_pre_2026_features'] = 'PASS'
checks['all_checks'] = 'PASS'
(R / 'verification.json').write_text(json.dumps(checks, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps(checks, indent=2, ensure_ascii=False))
