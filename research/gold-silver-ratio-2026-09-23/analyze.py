"""Exploratory predictive check, not an executable investment backtest."""
from pathlib import Path
import argparse
import json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('--cutoff',default='2025-12')
args=parser.parse_args()
suffix='' if args.cutoff=='2025-12' else '_'+args.cutoff
SOURCE = ROOT / 'sources' / 'worldbank_monthly.xlsx'
raw = pd.read_excel(SOURCE, sheet_name='Monthly Prices', header=4)
first = raw.columns[0]
raw = raw[raw[first].astype(str).str.match(r'^\d{4}M\d{2}$')].copy()
df = raw[[first, 'Gold', 'Silver']].rename(columns={first:'month', 'Gold':'gold', 'Silver':'silver'})
df['date'] = pd.to_datetime(df['month'], format='%YM%m')
df = df.set_index('date').drop(columns='month').apply(pd.to_numeric, errors='raise')
assert not df.isna().any().any()
assert df.index.is_unique and df.index.is_monotonic_increasing
assert (np.diff(df.index.to_period('M').asi8) == 1).all()
assert (df > 0).all().all()
df['ratio'] = df.gold / df.silver
df.to_csv(ROOT / 'gold_silver_monthly.csv', float_format='%.10g')

# Avoid the fixed monetary regime and freeze complete evaluation outcomes at 2025-12.
# 2026 observations are kept for description only, not for choosing model specifications.
d = df.loc['1972-01':args.cutoff].copy()
lg, ls = np.log(d.gold), np.log(d.silver)
d['gold_1m'] = lg.diff()
d['gold_12m'] = lg.diff(12)
d['silver_1m'] = ls.diff()
d['log_ratio'] = np.log(d.ratio)
models = {
    'historical_mean': [],
    'ratio_only': ['log_ratio'],
    'gold_own_history': ['gold_1m', 'gold_12m'],
    'gold_plus_silver': ['gold_1m', 'gold_12m', 'silver_1m', 'log_ratio'],
}
periods = [('1972-1999','1972-01','1999-12'),('2000-2012','2000-01','2012-12'),('2013-2025','2013-01','2025-12')]
correlations = []
predictions = []
for h in [1,3,12]:
    # x(t) predicts log(P(t+1+h)/P(t+1)); monthly averages do not represent executable prices.
    target = lg.shift(-1-h) - lg.shift(-1)
    relative = (ls.shift(-1-h) - ls.shift(-1)) - target
    for label, start, end in periods:
        sub = pd.concat([d[['log_ratio','silver_1m','gold_1m']], target.rename('future_gold'), relative.rename('future_silver_minus_gold')], axis=1).loc[start:end].dropna()
        correlations.append({'period':label,'horizon_months':h,'n':len(sub),'corr_ratio_gold':sub.log_ratio.corr(sub.future_gold),'corr_ratio_relative':sub.log_ratio.corr(sub.future_silver_minus_gold),'corr_silver_gold':sub.silver_1m.corr(sub.future_gold)})
    for i, date in enumerate(d.index):
        if date < pd.Timestamp('2000-01-01') or pd.isna(target.iloc[i]):
            continue
        # Only training labels whose final observation has already occurred at t are admitted.
        cutoff = i - 1 - h
        if cutoff < 0:
            continue
        feature_union = ['gold_1m','gold_12m','silver_1m','log_ratio']
        train = d.iloc[:cutoff+1][feature_union].join(target.rename('target')).dropna()
        if len(train) < 120:
            continue
        assert d.index[cutoff+1+h] <= date
        for name, columns in models.items():
            if columns:
                x = np.column_stack([np.ones(len(train)), train[columns].to_numpy()])
                coeff = np.linalg.lstsq(x, train.target.to_numpy(), rcond=None)[0]
                forecast = np.r_[1., d.loc[date, columns].to_numpy()] @ coeff
            else:
                forecast = train.target.mean()
            predictions.append({'date':str(date.date()),'horizon_months':h,'model':name,'forecast':float(forecast),'actual':float(target.iloc[i]),'training_n':len(train)})

pred = pd.DataFrame(predictions)
pred.to_csv(ROOT / f'walk_forward_predictions{suffix}.csv', index=False)
oos = []
for h in [1,3,12]:
    for label, start, end in [('2000-2025','2000-01-01','2025-12-31'),('2000-2012','2000-01-01','2012-12-31'),('2013-2025','2013-01-01','2025-12-31')]:
        a = pred[(pred.horizon_months==h)&(pred.date>=start)&(pred.date<=end)].copy()
        a['error2']=(a.forecast-a.actual)**2
        mse = a.groupby('model').error2.mean()
        for model in models:
            b = a[a.model==model]
            oos.append({'period':label,'horizon_months':h,'model':model,'n':len(b),'mse':mse[model], 'r2_vs_mean':1-mse[model]/mse['historical_mean'],'r2_vs_gold_own':1-mse[model]/mse['gold_own_history'],'direction_accuracy':float((np.sign(b.forecast)==np.sign(b.actual)).mean())})

descriptive=[]
for label, start, end in [('1972-1979','1972','1979'),('1980-1989','1980','1989'),('1990-1999','1990','1999'),('2000-2009','2000','2009'),('2010-2019','2010','2019'),('2020-2025','2020','2025')]:
    s=df.loc[start:end,'ratio']
    descriptive.append({'period':label,'n':len(s),'mean':s.mean(),'median':s.median(),'min':s.min(),'max':s.max()})

ret = np.log(df[['gold','silver']]).diff().loc['1972':'2025']
examples=[]
for start,end in [('2011-04','2011-09'),('2020-03','2020-08'),('2008-03','2008-10'),('2025-04','2025-12')]:
    a,b=df.loc[start].iloc[0],df.loc[end].iloc[0]
    examples.append({'start':start,'end':end,'gold_return':b.gold/a.gold-1,'silver_return':b.silver/a.silver-1,'ratio_start':a.ratio,'ratio_end':b.ratio})

description = pd.read_excel(SOURCE,sheet_name='Description',header=None)
desc_rows=description[description.apply(lambda r:r.astype(str).str.contains(r'Gold|Silver',case=False,regex=True).any(),axis=1)]
mismatch=pd.read_excel(SOURCE,sheet_name='Mismatch Details',header=3)
metal_mismatches=mismatch[mismatch.astype(str).apply(lambda c:c.str.fullmatch('Gold|Silver',case=False)).any(axis=1)]
out={
 'source':'World Bank Pink Sheet, downloaded 2026-09-23; workbook dated 2026-09-02',
 'data_start':str(df.index.min().date()),'data_end':str(df.index.max().date()),'raw_n':len(df),
 'evaluation_price_cutoff':args.cutoff,'signal_start':'1972-01','oos_start':'2000-01',
 'method':f'Monthly average USD/troy oz prices. One-month gap. Expanding OLS with intercept; no fitting on unavailable target outcomes. Complete outcomes through {args.cutoff}. Period labels indicate fixed requested signal-date windows and may truncate at available outcomes. Exploratory, no formal significance inference or transaction-cost backtest.',
 'contemporaneous_monthly_return_correlation':ret.gold.corr(ret.silver),
 'monthly_volatility_gold':ret.gold.std(),'monthly_volatility_silver':ret.silver.std(),
 'latest_month':{k:float(v) for k,v in df.iloc[-1].items()},
 'source_description':desc_rows.fillna('').values.tolist(),
 'source_mismatch_sheet_gold_silver_rows':metal_mismatches.fillna('').to_dict('records'),
 'descriptive':descriptive,'correlations':correlations,'oos':oos,'historical_examples':examples,
 'limitations':['Monthly averages smooth returns and are not tradable prices.','Historical-vintage publication/revision database unavailable; pseudo out-of-sample only.','Overlapping 3m/12m targets are dependent; no naive t-tests.','No USD/rate/industrial controls, no nonlinear or volatility forecast model.','Model/period choices fixed before the first result, but this is exploratory rather than preregistered research.','Failure of tested specifications cannot exclude usefulness of all silver-based signals.']
}
(ROOT/f'results{suffix}.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print('CUTOFF',args.cutoff)
print(pd.DataFrame(oos).query("period == '2000-2025'").to_string(index=False))
print('SOURCE DESCRIPTION',out['source_description'])
