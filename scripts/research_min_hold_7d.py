"""Re-test leading gold strategies with FIFO lots locked for seven trading days."""
from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]; COST=.001; MIN_HOLD=7
def load(path,col):return pd.read_csv(path,parse_dates=["date"],na_values=["."]).set_index("date")[col].astype(float)
def rsi(p,n=14):
 d=p.diff();u=d.clip(lower=0).rolling(n).mean();v=-d.clip(upper=0).rolling(n).mean();return 100-100/(1+u/v.replace(0,np.nan))
def lock_lots(desired,min_hold=7):
    """Each weight increase is a lot; only lots aged >= min_hold sessions can be reduced."""
    lots=[];out=[]
    for i,want in enumerate(desired.fillna(0).clip(0,1)):
        current=sum(a for _,a in lots)
        if want>current+1e-12: lots.append([i,want-current])
        elif want<current-1e-12:
            need=current-want
            for lot in lots:
                if need<=1e-12:break
                if i-lot[0]>=min_hold and lot[1]>0:
                    sold=min(need,lot[1]);lot[1]-=sold;need-=sold
            lots=[lot for lot in lots if lot[1]>1e-12]
        out.append(sum(a for _,a in lots))
    return pd.Series(out,index=desired.index)
def bt(p,target,start,end,locked):
    idx=p.loc[start:end].index;q=p.reindex(idx);desired=target.reindex(idx).shift(1).fillna(0)
    w=lock_lots(desired,MIN_HOLD) if locked else desired.clip(0,1)
    r=q.pct_change().fillna(0);turn=w.diff().abs().fillna(w.abs());sr=w*r-COST*turn;eq=(1+sr).cumprod();dd=eq/eq.cummax()-1;yrs=max((idx[-1]-idx[0]).days/365.25,1/252)
    ann=(eq.iloc[-1]**(1/yrs)-1);downside=np.sqrt((sr.clip(upper=0)**2).mean())*np.sqrt(252)
    runs=[];run=0
    for underwater in (dd<0):
        run=run+1 if underwater else 0;runs.append(run)
    avg_w=w.mean();static_final=(1-COST*avg_w)*(1+avg_w*r).cumprod().iloc[-1]
    static_return=(static_final-1)*100
    maxdd=dd.min()*100
    return {"return_pct":round((eq.iloc[-1]-1)*100,2),"annualized_return_pct":round(ann*100,2),"max_drawdown_pct":round(maxdd,2),"average_weight_pct":round(avg_w*100,2),"turnover":round(turn.sum(),2),"last_executed_weight_pct":round(w.iloc[-1]*100,2),"calmar":round(ann/abs(maxdd/100),3) if maxdd<0 else None,"sortino":round(ann/downside,3) if downside>0 else None,"max_underwater_days":int(max(runs)),"matched_exposure_alpha_pct":round((eq.iloc[-1]-1)*100-static_return,2)}
def equity_curve(p,target,start,end):
    idx=p.loc[start:end].index;q=p.reindex(idx);desired=target.reindex(idx).shift(1).fillna(0)
    w=lock_lots(desired,MIN_HOLD);r=q.pct_change().fillna(0);turn=w.diff().abs().fillna(w.abs())
    return (1+w*r-COST*turn).cumprod(),w
def main():
 g=load(ROOT/"data/raw/market/london_gold_fixing.csv","london_gold_usd_oz")
 aux=pd.concat({"dxy":load(ROOT/"data/raw/market/yahoo_dollar_index.csv","close"),"real":load(ROOT/"data/raw/macro/fred_us_10y_real_yield.csv","value"),"nominal":load(ROOT/"data/raw/macro/fred_us_10y_nominal_yield.csv","value"),"vix":load(ROOT/"data/raw/macro/fred_vix_close.csv","value"),"spx":load(ROOT/"data/raw/market/yahoo_sp500.csv","close"),"tlt":load(ROOT/"data/raw/market/yahoo_long_treasury_etf.csv","close"),"usdcny":load(ROOT/"data/raw/market/yahoo_usd_cny.csv","close"),"breakeven":load(ROOT/"data/raw/macro/fred_us_10y_breakeven_inflation.csv","value")},axis=1).sort_index().ffill().reindex(g.index).ffill()
 ret=g.pct_change();vol20=ret.rolling(20).std()*np.sqrt(252);risk12=(.12/vol20).clip(.25,1);risk11=(.11/vol20).clip(.25,.75);ma50=g.rolling(50).mean();ma100=g.rolling(100).mean();ma150=g.rolling(150).mean();ma200=g.rolling(200).mean();ma250=g.rolling(250).mean()
 dxy60=aux.dxy.pct_change(60);real60=aux.real.diff(60);vix20=aux.vix.pct_change(20)
 C={}
 C["macro_three_vote"] = risk12.where((g>ma150)&(((dxy60<0).astype(int)+(real60<0).astype(int)+(vix20<=.15).astype(int))>=3),0)
 C["stable_vol_trend"] = risk11.where((g>ma200)&((vol20.rolling(20).std())<(vol20.rolling(20).std()).rolling(126).median()),0)
 C["dollar_real_combo"] = risk12.where((g>ma150)&(dxy60<0)&(real60<0),0)
 C["dollar_weakness"] = risk12.where((g>ma150)&(dxy60<0),0)
 C["nominal_yield_falling"] = risk11.where((g>ma100)&(aux.nominal.diff(40)<0),0)
 C["real_yield_falling"] = risk12.where((g>ma150)&(real60<0),0)
 C["vix_calm_trend"] = risk12.where((g>ma150)&(aux.vix<25),0)
 total_votes=(dxy60<0).astype(int)+(real60<0).astype(int)+(aux.breakeven.diff(60)>0).astype(int)+(aux.vix<25).astype(int)+(g>ma200).astype(int)+(ma50>ma200).astype(int)+(g.pct_change(60)>0).astype(int)
 C["seven_factor_vote"] = risk12.where(total_votes>=5,0)
 C["trend_ma100_slope40"] = (.14/(ret.rolling(20).std()*np.sqrt(252))).clip(.25,1).where((g>ma100)&(ma100.diff(40)>0),0)
 long_ok=g>ma250;short_ok=g.pct_change(60)>0;dual=pd.Series(0.,index=g.index);dual[long_ok^short_ok]=.25;dual[long_ok&short_ok]=risk12.clip(.5,1)[long_ok&short_ok];C["dual_ma250_mom60"]=dual
 C["low_vol_trend"] = (.10/vol20).clip(.25,.75).where((g>ma200)&(vol20<.22),0)
 C["safe_haven_regime"] = risk12.where((g>ma150)&(aux.spx<aux.spx.rolling(200).mean())&(aux.vix>20),0)
 C["gold_bond_relative"] = risk11.where(((g/aux.tlt)>(g/aux.tlt).rolling(100).mean())&(g>ma100),0)
 rr=rsi(g);entry=(rr.shift(1)<30)&(rr>=30)&(g>ma200);exit_=(rr>65)|(g<ma200);state=0;vals=[]
 for dt in g.index:
  if state and exit_.loc[dt]:state=0
  elif not state and entry.loc[dt]:state=.5
  vals.append(state)
 C["rsi_oversold_rebound"]=pd.Series(vals,index=g.index)
 C["cny_confirmation"] = risk11.where((g>ma150)&(aux.usdcny.pct_change(60)>=0),0)
 assert len(C)==15
 splits={"train":("2020-01-01","2023-12-31"),"validation":("2024-01-01","2024-12-31"),"blind":("2025-01-01","2026-08-27"),"ytd_2026":("2026-01-01","2026-08-27"),"recent":("2026-02-01","2026-08-27"),"full":("2020-01-01","2026-08-27")}
 rows=[]
 for name,target in C.items():
  row={"strategy":name,"raw_current_signal_pct":round(float(target.iloc[-1])*100,2)}
  for split,(a,b) in splits.items():
   locked=bt(g,target,a,b,True);free=bt(g,target,a,b,False)
   for k,v in locked.items():row[f"{split}_{k}"]=v
   row[f"{split}_return_change_vs_free_pct"]=round(locked["return_pct"]-free["return_pct"],2)
   row[f"{split}_drawdown_change_vs_free_pct"]=round(locked["max_drawdown_pct"]-free["max_drawdown_pct"],2)
  row["preblind_score"]=round(row["train_annualized_return_pct"]+row["validation_annualized_return_pct"]+2*(row["train_max_drawdown_pct"]+row["validation_max_drawdown_pct"])-.25*abs(row["train_annualized_return_pct"]-row["validation_annualized_return_pct"]),2)
  rows.append(row)
 df=pd.DataFrame(rows);eligible=df[(df.train_return_pct>0)&(df.validation_return_pct>0)].sort_values("preblind_score",ascending=False)
 finalists=["macro_three_vote","dollar_real_combo","stable_vol_trend","dollar_weakness","nominal_yield_falling"]
 score=df[df.strategy.isin(finalists)].copy()
 score["drawdown_gate_pass"]=score.blind_max_drawdown_pct>=-10
 metrics=[("blind_calmar",.40,True),("blind_sortino",.25,True),("blind_annualized_return_pct",.15,True),("blind_max_underwater_days",.10,False),("blind_matched_exposure_alpha_pct",.10,True)]
 score["composite_score"]=0.0
 for col,weight,higher in metrics:
  pct=score[col].rank(pct=True,ascending=higher)*100
  score["composite_score"]+=weight*pct
 score.loc[~score.drawdown_gate_pass,"composite_score"]=0
 score=score.sort_values("composite_score",ascending=False)
 all_score=df.copy()
 all_score["drawdown_gate_pass"]=all_score.blind_max_drawdown_pct>=-10
 all_score["composite_score"]=0.0
 expanded_metrics=[("blind_calmar",.25,True),("blind_sortino",.15,True),("blind_return_pct",.15,True),("blind_max_drawdown_pct",.15,True),("ytd_2026_return_pct",.10,True),("ytd_2026_max_drawdown_pct",.10,True),("blind_max_underwater_days",.05,False),("blind_matched_exposure_alpha_pct",.05,True)]
 for col,weight,higher in expanded_metrics:
  pct=all_score[col].rank(pct=True,ascending=higher)*100
  all_score["composite_score"]+=weight*pct
 all_score.loc[~all_score.drawdown_gate_pass,"composite_score"]=0
 all_score=all_score.sort_values(["composite_score","blind_calmar"],ascending=False)
 df.sort_values("preblind_score",ascending=False).to_csv(ROOT/"data/derived/min_hold_7d_research.csv",index=False)
 report={"minimum_holding_trading_days":7,"early_redemption_fee_avoided_pct":1.5,"normal_weight_change_cost":COST,"candidate_count":len(C),"top5_preblind":eligible.head(5).to_dict("records"),"five_strategy_composite_ranking":score.to_dict("records"),"top10_composite_ranking":all_score.head(10).to_dict("records"),"all":df.to_dict("records")}
 (ROOT/"reports/min_hold_7d_research.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
 baseline_names=["low_vol_trend","macro_three_vote","dollar_weakness"]
 curves={};weights={};individual=[]
 for name in baseline_names:
  eq,w=equity_curve(g,C[name],"2020-01-01","2026-08-27");curves[name]=eq;weights[name]=w
  dd=eq/eq.cummax()-1
  individual.append({"strategy":name,"initial_cny":50000.0,"final_cny":round(float(50000*eq.iloc[-1]),2),"return_pct":round(float((eq.iloc[-1]-1)*100),2),"max_drawdown_pct":round(float(dd.min()*100),2),"current_signal_weight_pct":round(float(C[name].iloc[-1]*100),2)})
 equity_df=pd.DataFrame(curves);weight_df=pd.DataFrame(weights);portfolio_cny=50000*equity_df.sum(axis=1);portfolio_dd=portfolio_cny/portfolio_cny.cummax()-1
 detail=pd.concat({"equity":equity_df,"weight":weight_df},axis=1);detail[('portfolio','cny')]=portfolio_cny
 detail.to_csv(ROOT/"data/derived/baseline_v2_2020_equity.csv",index_label="date")
 requested_individual=[];requested_curves={}
 for name in baseline_names:
  eq,_=equity_curve(g,C[name],"2025-10-01","2026-08-27");requested_curves[name]=eq;dd=eq/eq.cummax()-1
  requested_individual.append({"strategy":name,"initial_cny":50000.0,"final_cny":round(float(50000*eq.iloc[-1]),2),"return_pct":round(float((eq.iloc[-1]-1)*100),2),"max_drawdown_pct":round(float(dd.min()*100),2)})
 requested_df=pd.DataFrame(requested_curves);requested_portfolio=50000*requested_df.sum(axis=1);requested_dd=requested_portfolio/requested_portfolio.cummax()-1
 benchmark=g.loc["2025-10-01":"2026-08-27"];benchmark_eq=benchmark/benchmark.iloc[0];benchmark_dd=benchmark_eq/benchmark_eq.cummax()-1
 requested_output=100*requested_df.copy();requested_output["portfolio"]=100*requested_portfolio/150000;requested_output["gold"]=100*benchmark_eq
 requested_output.to_csv(ROOT/"data/derived/baseline_v2_2025_10_comparison.csv",index_label="date")
 baseline_report={"period":[str(portfolio_cny.index[0].date()),str(portfolio_cny.index[-1].date())],"initial_total_cny":150000.0,"individual":individual,"portfolio":{"final_cny":round(float(portfolio_cny.iloc[-1]),2),"return_pct":round(float((portfolio_cny.iloc[-1]/150000-1)*100),2),"max_drawdown_pct":round(float(portfolio_dd.min()*100),2)},"requested_2025_10_01":{"period":[str(requested_portfolio.index[0].date()),str(requested_portfolio.index[-1].date())],"individual":requested_individual,"portfolio":{"final_cny":round(float(requested_portfolio.iloc[-1]),2),"return_pct":round(float((requested_portfolio.iloc[-1]/150000-1)*100),2),"max_drawdown_pct":round(float(requested_dd.min()*100),2)},"london_gold_buy_hold":{"final_cny":round(float(150000*benchmark_eq.iloc[-1]),2),"return_pct":round(float((benchmark_eq.iloc[-1]-1)*100),2),"max_drawdown_pct":round(float(benchmark_dd.min()*100),2)}}}
 (ROOT/"reports/baseline_v2_2020_backtest.json").write_text(json.dumps(baseline_report,ensure_ascii=False,indent=2),encoding="utf-8")
 print(json.dumps({"eligible":len(eligible),"top5":report["top5_preblind"]},ensure_ascii=False,indent=2))
if __name__=="__main__":main()
