from utils import *
import sys
sys.path.insert(0,str(BASE/'cycles'))
import common as old

def series_json(path):
    a=json.loads(path.read_text())['chart']['result'][0]
    return pd.Series(a['indicators']['adjclose'][0]['adjclose'],index=pd.to_datetime(a['timestamp'],unit='s',utc=True).tz_localize(None).normalize()).dropna()

d=read_panel(BASE/'cycles/daily_primary_panel.csv')
g=np.log(d.gold);s=np.log(d.silver);q=g-s;rg=g.diff();rs=s.diff();rq=q.diff()
for h in [1,5,20]:
    d[f'gret{h}']=g.diff(h);d[f'sret{h}']=s.diff(h);d[f'qret{h}']=q.diff(h)
    power=rs.pow(2).rolling(h).mean()*252
    d[f'svol{h}']=np.log(np.sqrt(power.where(power>0)))
d['qabs1']=rq.abs();d['qz1']=(rq-rq.rolling(252).mean().shift(1))/rq.rolling(252).std().shift(1)
d['qzabs1']=d.qz1.abs();d['qsquare1']=rq**2
d['speed5_abs']=d.qret5.abs();d['qpos5']=d.qret5.clip(lower=0);d['qneg5']=(-d.qret5).clip(lower=0)
d['qpos_shock']=d.qz.clip(lower=0);d['qneg_shock']=(-d.qz).clip(lower=0)
d['qabs_squared']=d.qabs**2
d['gvz_high']=(d.log_gvz>d.log_gvz.rolling(252).median().shift(1)).astype(float)
d.loc[d.log_gvz.rolling(252).count()<252,'gvz_high']=np.nan
d['qabs_high_gvz']=d.qabs*d.gvz_high
d['gold_down']=d.gret5.clip(upper=0);d['qabs_gold_down']=d.qabs*d.gold_down
extreme=d.qz.abs()>1.5
d['extreme_first']=(extreme&~extreme.shift(1,fill_value=False)).astype(float)
d['extreme_continues']=(extreme&extreme.shift(1,fill_value=False)).astype(float)
for h in [5,20]:
    d[f'future_logvar{h}']=2*d[f'future_vol{h}']
    threshold=2*np.exp(d.gvol20)*np.sqrt(h/252)
    valid=d[f'future_return{h}'].notna()
    d[f'tail_down{h}']=(d[f'future_return{h}']<-threshold).astype(float).where(valid)
    d[f'tail_up{h}']=(d[f'future_return{h}']>threshold).astype(float).where(valid)
m=old.macro_panel(d.index)
for name,col in [('dollar0','dollar'),('sp0','sp500')]:d[name]=np.log(m[col]).diff(20)
d['real0']=m.real.diff(20);d['vix0']=np.log(m.vix).diff(20);d['gvz0']=np.log(m.gvz).diff(20)
for metal,file in [('copper','HG_F.json'),('oil','BZ_F.json')]:
    p=old.align(series_json(ROOT/'sources'/file),d.index)
    d[metal+'0']=np.log(p).diff(20);d[metal+'20']=d[metal+'0'].shift(1)
b=pd.read_csv(ROOT/'sources/breakeven_snapshot.csv',parse_dates=['date']).set_index('date').value
b=old.align(pd.to_numeric(b,errors='coerce'),d.index)
d['breakeven0']=b.diff(20);d['breakeven20']=d.breakeven0.shift(1)
d['vix_up']=d.vix0.clip(lower=0);d['vix_down']=d.vix0.clip(upper=0)
d.to_csv(ROOT/'daily_panel.csv')

# All trader-class features share a conservative availability clock.
cot=read_panel(BASE/'cycles/round2_cot_panel.csv')
raw=pd.DataFrame(json.loads((BASE/'cycles/sources/cot_full_2025.json').read_text()))
for code,metal in [('088691','g'),('084691','s')]:
    a=raw[raw.cftc_contract_market_code==code].copy();a.index=pd.to_datetime(a.report_date_as_yyyy_mm_dd)
    a=a.sort_index();oi=pd.to_numeric(a.open_interest_all)
    cot[metal+'_spread']=pd.to_numeric(a.m_money_positions_spread)/oi
    cot[metal+'_oi_delta']=oi.pct_change()
    net=cot[metal+'_mm_net']
    cot[metal+'_crowd_z']=(net-net.rolling(156).mean().shift(1))/net.rolling(156).std().shift(1)
    cot[metal+'_both_contract']=((cot[metal+'_long_delta']<0)&(cot[metal+'_short_delta']<0)).astype(float)
cot['relative_crowding']=cot.g_crowd_z-cot.s_crowd_z
cot.to_csv(ROOT/'cot_panel.csv')
features=[c for c in cot if c.endswith(('_net','_net_delta','_spread','_oi_delta','_crowd_z','_both_contract','_long_delta','_short_delta','_tail'))]+['relative_crowding']
features=list(dict.fromkeys(features));cs=cot[features].copy();cs['cot_asof']=cs.index
cs.index=cs.index+pd.Timedelta(days=10);cs.index.name='available'
w=old.weekly(d)
w=pd.merge_asof(w.reset_index(),cs.reset_index(),left_on='date',right_on='available',direction='backward').set_index('date')
age=(w.index-pd.to_datetime(w.cot_asof)).dt.days
blackouts=json.loads((BASE/'cycles/round2_results.json').read_text())['excluded_observation_windows']
for a,b in blackouts:w.loc[a:b,features]=np.nan
w.loc[age>24,features]=np.nan
w.to_csv(ROOT/'weekly_panel.csv')

# Synchronized intraday observations. Last available complete date is fixed before modelling.
audits=[]
def hourly(symbol):
    a=json.loads((BASE/f'unresolved/sources/{symbol}_hourly.json').read_text())['chart']['result'][0]
    h=pd.DataFrame(a['indicators']['quote'][0],index=pd.to_datetime(a['timestamp'],unit='s',utc=True).tz_convert('America/New_York'))
    assert h.index.is_unique and h.index.is_monotonic_increasing
    h=h.loc[h.index.date<=pd.Timestamp('2026-09-22').date()]
    h['date']=h.index.tz_localize(None).normalize();h['slot']=h.index.hour*60+h.index.minute
    return h

gvz=pd.read_csv(BASE/'cycles/sources/gvz.csv',parse_dates=['DATE']).set_index('DATE').GVZ
vix=old.yahoo_series(BASE/'cycles/sources/extended_^VIX.json','vix')
for pair,syms in [('GLD_SLV',['GLD','SLV']),('IAU_SIVR',['IAU','SIVR'])]:
    hh=[]
    for sym,metal in zip(syms,['g','s']):
        a=hourly(sym);hh.append(a[['open','close','volume','date','slot']].rename(columns={c:metal+'_'+c for c in ['open','close','volume']}))
    h=hh[0].join(hh[1].drop(columns=['date','slot']),how='inner')
    full_days=[];all_days=[];bar_outputs=[]
    expected=list(range(570,931,60))
    for date,aa in h.groupby('date'):
        a=aa[aa.slot.isin(expected)].copy()
        full=(a.slot.tolist()==expected and a[['g_open','g_close','s_open','s_close']].notna().all().all())
        # A daily last quote is retained for next-day overnight measurement even on a half day.
        closes=aa[['g_close','s_close']].dropna()
        opens=aa[aa.slot.eq(570)][['g_open','s_open']].dropna()
        row={'date':date,'full_day':full,'valid_bars':int(a[['g_close','s_close']].notna().all(axis=1).sum()),
             'zero_volume_bars':int(((a.g_volume==0)|(a.s_volume==0)).sum()),
             'g_close':closes.g_close.iloc[-1] if len(closes) else np.nan,'s_close':closes.s_close.iloc[-1] if len(closes) else np.nan,
             'g_open':opens.g_open.iloc[0] if len(opens) else np.nan,'s_open':opens.s_open.iloc[0] if len(opens) else np.nan}
        if full:
            for metal in ['g','s']:
                ret=np.log(a[metal+'_close']).diff()
                ret.iloc[0]=np.log(a[metal+'_close'].iloc[0]/a[metal+'_open'].iloc[0])
                a[metal+'r']=ret
                row[metal+'rv']=float((ret**2).sum());row[metal+'oc']=float(ret.sum())
            a['qr']=a.gr-a.sr
            a['minutes']=np.where(a.slot.eq(930),30,60)
            row['qrv']=float((a.qr**2).sum());row['gscov']=float((a.gr*a.sr).sum())
            row['qoc']=float(a.qr.sum());bar_outputs.append(a)
            full_days.append(date)
        all_days.append(row)
    z=pd.DataFrame(all_days).set_index('date')
    # Official daily closes prevent a partial intraday day from becoming a false closing quote.
    close_audit=[]
    for metal,symbol in zip(['g','s'],syms):
        daily_close=series_json(ROOT/'sources'/f'{symbol}_daily.json').reindex(z.index)
        prior=z[metal+'_close'].copy()
        z[metal+'_close']=daily_close
        close_audit.append({'metal':metal,'largest_hourly_last_vs_daily_close_gap_pct':float((100*(prior/daily_close-1)).abs().max()),
                            'missing_daily_closes':int(daily_close.isna().sum())})
    for metal in ['g','s']:
        z[metal+'overnight']=np.log(z[metal+'_open']/z[metal+'_close'].shift(1))
        z[metal+'totalrv']=z[metal+'rv']+z[metal+'overnight']**2
        z[metal+'ret']=np.log(z[metal+'_close']).diff()
    z['log_ratio']=np.log(z.g_close/z.s_close);z['qret']=z.gret-z.sret
    for metal in ['g','s']:
        for k in [1,5,22]:
            z[f'{metal}rv{k}']=np.log(z[metal+'rv'].rolling(k).mean())
    z['q_abs']=z.qret.abs()
    z['q_scaled']=z.qret.abs()/np.sqrt(z.qrv.rolling(22).mean().shift(1))
    z['q_pressure']=np.nan
    # Forecast ratio level using information strictly before the day being scored.
    for i in range(127,len(z)):
        lag=z.log_ratio.iloc[i-127:i-1].to_numpy();y=z.log_ratio.iloc[i-126:i].to_numpy()
        if not np.isfinite(np.r_[lag,y,z.log_ratio.iloc[i],z.log_ratio.iloc[i-1]]).all():continue
        x=np.column_stack([np.ones(126),lag]);b=np.linalg.lstsq(x,y,rcond=None)[0]
        sd=np.sqrt(np.mean((y-x@b)**2))
        z.loc[z.index[i],'q_pressure']=abs(z.log_ratio.iloc[i]-np.r_[1,z.log_ratio.iloc[i-1]]@b)/sd
    z['log_gvz']=np.log(old.align(gvz,z.index)).shift(1)
    z['log_vix']=np.log(old.align(vix,z.index)).shift(1)
    z['gret5']=np.log(z.g_close).diff(5)
    for gap in [0,1]:
        for k in [1,5]:
            for typ in ['rv','totalrv']:
                # Exactly the next k trading dates, optionally leaving one full trading date unused.
                z[f'future_{typ}_{k}_gap{gap}']=np.log(z['g'+typ].rolling(k).mean().shift(-(k+gap)))
            z[f'end_{k}_gap{gap}']=pd.Series(z.index,index=z.index).shift(-(k+gap))
    bars=pd.concat(bar_outputs);bars.index.name='timestamp'
    for metal in ['g','s']:
        for lag in [1,2]:bars[f'{metal}lag{lag}']=bars.groupby('date')[metal+'r'].shift(lag)
    bars.to_csv(ROOT/f'hourly_{pair}.csv');z.to_csv(ROOT/f'hourly_daily_{pair}.csv')
    audits.append({'pair':pair,'calendar_trading_days':len(z),'complete_days':len(full_days),'bars_on_complete_days':len(bars),
                   'first':str(z.index[0].date()),'last':str(z.index[-1].date()),'excluded_dates':z.index[~z.full_day].strftime('%Y-%m-%d').tolist(),
                   'zero_volume_bars_on_complete_days':int(z.loc[z.full_day,'zero_volume_bars'].sum()),
                   'target_valid_next1':int(z.future_rv_1_gap0.notna().sum()),'target_valid_next5':int(z.future_rv_5_gap0.notna().sum()),
                   'daily_close_crosscheck':close_audit})
save('preparation_audit.json',{'daily_rows':len(d),'weekly_rows':len(w),'cot_rows':len(cot),'hourly':audits,'last_complete_hourly_date':'2026-09-22'})
print(json.dumps(audits,indent=2))
