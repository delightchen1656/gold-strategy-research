"""Event-driven backtest using product-native execution and fee rules from 2021."""
from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/"research"/"real-product-rules-2021-present"
INITIAL=50_000.0
OZ_TO_GRAM=31.1034768
BUY_FEE=1-1/1.015  # exact front-end fee drag when quoted subscription fee is 1.5%

def load(path, column):
    return pd.read_csv(path,parse_dates=["date"],na_values=["."]).set_index("date")[column].astype(float).sort_index()

def features():
    gold=load(ROOT/"data/raw/market/london_gold_fixing.csv","london_gold_usd_oz").dropna()
    # The public LBMA file available during this run ended before these observations.
    extra=pd.Series({pd.Timestamp("2026-09-01"):4367.25,pd.Timestamp("2026-09-02"):4308.70,pd.Timestamp("2026-09-03"):4434.25})
    gold=pd.concat([gold,extra]).groupby(level=0).last().sort_index()
    aux=pd.concat({
        "dxy":load(ROOT/"data/raw/market/yahoo_dollar_index.csv","close"),
        "real":load(ROOT/"data/raw/macro/fred_us_10y_real_yield.csv","value"),
        "vix":load(ROOT/"data/raw/macro/fred_vix_close.csv","value"),
    },axis=1).sort_index().ffill().reindex(gold.index).ffill()
    return gold,aux

def periodic(raw, frequency="monthly"):
    periods=raw.index.to_period("M" if frequency=="monthly" else "W-FRI")
    dates=raw.groupby(periods).apply(lambda x:x.index.max())
    decision=pd.Series(np.nan,index=raw.index)
    for dt in dates: decision.loc[dt]=raw.loc[dt]
    return decision.ffill().fillna(0.0)

def trend(gold, ma, buffer):
    avg=gold.rolling(ma).mean();state=[];on=False
    for up,down in zip((gold>avg*(1+buffer)).fillna(False),(gold<avg*(1-buffer)).fillna(False)):
        if up:on=True
        elif down:on=False
        state.append(on)
    return pd.Series(state,index=gold.index)

def breakout_signal(gold, entry_days=60, exit_days=60, cap=.55):
    upper=gold.rolling(entry_days).max().shift(1);lower=gold.rolling(exit_days).min().shift(1)
    state=[];on=False
    for price,hi,lo in zip(gold,upper,lower):
        if pd.notna(hi) and price>=hi:on=True
        elif pd.notna(lo) and price<=lo:on=False
        state.append(on)
    return periodic(pd.Series(np.where(state,cap,0.0),index=gold.index))

def momentum_signal(gold, lookback=252, vol_window=60, target_vol=.14, cap=.60, floor=.25):
    mom=gold.pct_change(lookback);vol=gold.pct_change().rolling(vol_window).std()*np.sqrt(252)
    raw=pd.Series(np.where(mom>0,cap*(target_vol/vol).clip(floor,1.0),0.0),index=gold.index)
    return periodic(((raw/0.05).round()*0.05).clip(0,1))

def macro_signal(gold, aux, ma=90, buffer=.04, macro_days=60, vix_days=10, vix_limit=.30, cap=.60):
    active=trend(gold,ma,buffer)
    votes=(aux.dxy.pct_change(macro_days)<0).astype(int)+(aux.real.diff(macro_days)<0).astype(int)+(aux.vix.pct_change(vix_days)<=vix_limit).astype(int)
    return periodic(pd.Series(np.where(active&(votes>=1),cap,0.0),index=gold.index))

def executable_target(signal, price_index):
    changes=signal[signal.ne(signal.shift())]
    events={}
    for dt,value in changes.items():
        pos=price_index.searchsorted(dt,side="right")
        if pos<len(price_index):events[price_index[pos]]=float(value)
    out=[];state=0.0
    for dt in price_index:
        if dt in events:state=events[dt]
        out.append(state)
    return pd.Series(out,index=price_index)

def lots_and_fees(target,price,path):
    lots=[];weights=[];costs=[];turn=[]
    for dt,wanted in target.clip(0,1).items():
        current=sum(x[1] for x in lots);cost=0.0;tr=abs(wanted-current)
        if wanted>current+1e-12:
            amount=wanted-current;lots.append([dt,amount])
            if path=="fund":cost+=amount*BUY_FEE
            else:cost+=amount*2.5/price.loc[dt]
        elif wanted<current-1e-12:
            need=current-wanted
            for lot in lots:
                if need<=1e-12:break
                sold=min(need,lot[1]);lot[1]-=sold;need-=sold;age=(dt-lot[0]).days
                if path=="fund":cost+=sold*(.015 if age<7 else (.005 if age<30 else 0))
                else:cost+=sold*2.5/price.loc[dt]
            lots=[x for x in lots if x[1]>1e-12]
        weights.append(sum(x[1] for x in lots));costs.append(cost);turn.append(tr)
    return pd.Series(weights,index=target.index),pd.Series(costs,index=target.index),pd.Series(turn,index=target.index)

def simulate_real(price,signal,path):
    target=executable_target(signal,price.index);weight,cost,turn=lots_and_fees(target,price,path)
    ret=price.pct_change().fillna(0);daily=weight.shift(1).fillna(0)*ret-cost;equity=(1+daily).cumprod();dd=equity/equity.cummax()-1
    part=equity.loc["2021-01-01":];base=part.iloc[0];part=part/base;partdd=part/part.cummax()-1;years=(part.index[-1]-part.index[0]).days/365.25
    result={"start":part.index[0].date().isoformat(),"end":part.index[-1].date().isoformat(),"final_cny":round(INITIAL*part.iloc[-1],2),"return_pct":round((part.iloc[-1]-1)*100,2),"annualized_return_pct":round((part.iloc[-1]**(1/years)-1)*100,2),"max_drawdown_pct":round(partdd.min()*100,2),"average_weight_pct":round(weight.loc[part.index].mean()*100,2),"rebalance_days":int((turn.loc[part.index]>1e-12).sum()),"latest_weight_pct":round(weight.iloc[-1]*100,2)}
    detail=pd.DataFrame({"price":price,"target":target,"weight":weight,"cost":cost,"daily_return":daily,"equity":equity}).loc["2021-01-01":];detail["equity"]/=base
    return result,detail

def main():
    OUT.mkdir(parents=True,exist_ok=True);gold,aux=features();idx=gold.loc["2020-01-01":].index;fx=load(ROOT/"data/raw/market/yahoo_usd_cny.csv","close").reindex(idx).ffill().bfill()
    paths={"招商银行积存金代理":(gold.reindex(idx)*fx/OZ_TO_GRAM,"cmb"),"建信上海金ETF联接A":(load(ROOT/"data/raw/funds/009033_nav.csv","nav").dropna().loc["2020-08-05":"2026-09-04"],"fund")}
    signals={"策略1 价格通道突破":breakout_signal(gold),"策略2 波动率调整动量":momentum_signal(gold),"策略3 宏观状态":macro_signal(gold,aux)}
    results=[];details=[];splits=[]
    for strategy,signal in signals.items():
        for path,(price,code) in paths.items():
            res,det=simulate_real(price,signal,code);res.update({"strategy":strategy,"path":path});results.append(res);details.append(det.assign(strategy=strategy,path=path).reset_index(names="date"))
            for name,(a,b) in {"训练期 2021-2023":("2021-01-01","2023-12-31"),"验证期 2024":("2024-01-01","2024-12-31"),"盲测期 2025-2026":("2025-01-01","2026-12-31")}.items():
                p=det.loc[a:b].equity;p=p/p.iloc[0];splits.append({"strategy":strategy,"path":path,"split":name,"return_pct":round((p.iloc[-1]-1)*100,2),"max_drawdown_pct":round((p/p.cummax()-1).min()*100,2)})
    combined=[]
    for strategy in signals:
        pair=[x for x in results if x["strategy"]==strategy];final=sum(x["final_cny"] for x in pair);start=pd.Timestamp(max(x["start"] for x in pair));end=pd.Timestamp(min(x["end"] for x in pair));years=(end-start).days/365.25;growth=final/(2*INITIAL)
        combined.append({"strategy":strategy,"initial_cny":2*INITIAL,"final_cny":round(final,2),"return_pct":round((growth-1)*100,2),"annualized_return_pct":round((growth**(1/years)-1)*100,2),"average_weight_pct":round(sum(x["average_weight_pct"] for x in pair)/2,2),"latest_weight_pct":round(sum(x["latest_weight_pct"] for x in pair)/2,2)})
    pd.DataFrame(results).to_csv(OUT/"summary.csv",index=False);pd.DataFrame(combined).to_csv(OUT/"combined_summary.csv",index=False);pd.DataFrame(splits).to_csv(OUT/"split_validation.csv",index=False);pd.concat(details,ignore_index=True).to_csv(OUT/"daily_detail.csv",index=False)
    report={"period":"2021-present","execution":{"signal":"LBMA Gold Price AM month-end signal","both_paths":"first eligible product trading date strictly after signal date","fund_confirmation":"confirmation date does not change NAV attribution date","fund_redemption":"no artificial lock; FIFO fee by actual calendar holding days","cmb":"public mid-price proxy with ask=mid+2.5 and bid=mid-2.5 CNY/g"},"fees":{"fund_purchase_effective_drag":BUY_FEE,"fund_redemption":{"under_7_days":.015,"7_to_under_30_days":.005,"30_days_or_more":0}},"results":results,"combined":combined,"splits":splits,"limitations":["Historical CMB client quotes and intraday executable prices are unavailable, so CMB remains a proxy rather than a literal fill reconstruction.","Daily target-weight accounting approximates cash/share rounding and ignores minimum order size."]}
    (OUT/"result.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8");print(pd.DataFrame(results).to_string(index=False));print(pd.DataFrame(splits).to_string(index=False))
if __name__=="__main__":main()
