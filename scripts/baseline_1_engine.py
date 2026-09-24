"""Execution engine used by gold strategy Baseline 1.

No real accounts or orders are accessed. Outputs are isolated from legacy runs.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, asdict, replace
from pathlib import Path
import hashlib
import io
import json
import math
import sys
import urllib.request

import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research/baseline-1"
INPUT = OUT / "inputs"
INITIAL = 50_000.0
START = "2021-01-04"
END = "2026-09-07"
SPLITS = [("2021—2023", "2021-01-04", "2023-12-31"),
          ("2024", "2024-01-01", "2024-12-31"),
          ("2025—2026-09-07", "2025-01-01", END)]


def read_series(path, col):
    f = pd.read_csv(path, parse_dates=["date"], na_values=["."])
    if f.date.duplicated().any():
        raise ValueError(f"duplicate dates: {path}")
    return f.set_index("date")[col].astype(float).sort_index()


def prepare():
    INPUT.mkdir(parents=True, exist_ok=True)
    url = "https://www.westmetall.com/en/markdaten.php?action=table&field=USD_ozt_London&year=2026"
    dest = INPUT / "westmetall_2026.html"
    if not dest.exists():
        with urllib.request.urlopen(url, timeout=40) as response:
            dest.write_bytes(response.read())
    table = pd.read_html(io.StringIO(dest.read_text(encoding="utf-8")))[0]
    table.columns = ["date", "price"]
    table["date"] = pd.to_datetime(table.date, format="%d. %B %Y", errors="coerce")
    table["price"] = pd.to_numeric(table.price.astype(str).str.replace(",", ""), errors="coerce")
    extra = table.dropna().set_index("date").price.sort_index()
    old = read_series(ROOT / "data/raw/market/london_gold_fixing.csv", "london_gold_usd_oz")
    gold = pd.concat([old, extra]).groupby(level=0).last().sort_index().loc[:END]
    futures = read_series(ROOT / "data/raw/market/yahoo_gold_futures.csv", "close")
    ratio = gold / futures.reindex(gold.index).ffill()
    rejected = gold[(ratio < .8) | (ratio > 1.2)]
    gold = gold.drop(rejected.index)
    # Keep anomalies missing. No invented replacement prices and no backfill.
    gold.rename("gold_usd").to_csv(INPUT / "gold.csv", index_label="date")
    from collect_market_data import get
    fx_raw = INPUT / "yahoo_cny_chart.json"
    fx_url = "https://query1.finance.yahoo.com/v8/finance/chart/CNY%3DX?period1=1483228800&period2=1788825600&interval=1d&events=history"
    if not fx_raw.exists():
        fx_raw.write_bytes(get(fx_url))
    fx_json = json.loads(fx_raw.read_bytes())["chart"]["result"][0]
    zone = fx_json["meta"]["exchangeTimezoneName"]
    sessions = pd.to_datetime(fx_json["timestamp"],unit="s",utc=True).tz_convert(zone).tz_localize(None).normalize()
    fx = pd.Series(fx_json["indicators"]["quote"][0]["close"],index=sessions).dropna().sort_index().loc[:END]
    assert not fx.index.duplicated().any()
    fx.rename("close").to_csv(INPUT / "fx.csv", index_label="date")
    nav = pd.read_csv(ROOT / "data/raw/funds/009033_nav.csv", parse_dates=["date"]).set_index("date").sort_index()
    assert not nav.index.duplicated().any()
    assert (nav.nav == nav.acc_nav).all(), "Dividend/split handling required"
    # China product holiday calendar is proxied by the observed NAV calendar.
    # Missing London observations: value at latest known mid; never transact then.
    frame = nav.loc[:END].copy()
    frame["cmb_mid"] = (gold * fx.reindex(gold.index).ffill() / 31.1034768).reindex(frame.index).ffill()
    frame["cmb_trade"] = frame.index.isin(gold.index) & frame.subscription_status.eq("开放申购")
    frame["fund_buy"] = frame.subscription_status.eq("开放申购")
    frame["fund_sell"] = frame.redemption_status.eq("开放赎回")
    frame.to_csv(INPUT / "products.csv", index_label="date")
    audit = {"cutoff": END, "gold_source": url,
             "rejected_new_source_rows": {str(k.date()): v for k,v in rejected.items()},
             "nav_dividends_or_splits": 0, "fx_source":fx_url,"fx_timezone":zone,
             "fx_forward_filled_dates": [str(d.date()) for d in gold.loc[START:].index if d not in fx.index],
             "known_old_exclusions": ["2022-07-20", "2026-01-02"],
             "hashes": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in [INPUT / "gold.csv", INPUT / "products.csv", ROOT / "data/raw/funds/009033_nav.csv"]}}
    (OUT / "data_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k:v for k,v in audit.items() if k!="fx_forward_filled_dates"}, ensure_ascii=False, indent=2))


@dataclass(frozen=True)
class Spec:
    family: str
    horizon: int = 90
    exit_days: int = 20
    cap: float = .65
    vol_target: float = .12
    stop: float = .10
    frequency: str = "weekly"
    band: float = .10
    cooldown: int = 10


def registry():
    """Defined before evaluating 2025+. Modest grids; no holdout retuning."""
    result = []
    for family in ["channel", "trend_trail", "ensemble", "dual_momentum", "vol_trend", "pullback"]:
        for horizon in [60, 120, 180]:
            for cap in [.55, .65, .75, .85]:
                for stop in [.08, .12]:
                    for frequency in ["weekly", "monthly"]:
                        result.append(Spec(family, horizon=horizon, cap=cap, stop=stop, frequency=frequency))
    return result


def hysteresis(price, days, buffer=.02):
    avg = price.rolling(days).mean()
    state = False
    values = []
    for p, a in zip(price, avg):
        if p > a * (1 + buffer):
            state = True
        elif p < a * (1 - buffer):
            state = False
        values.append(float(state))
    return pd.Series(values, index=price.index)


def make_signal(spec, gold, product_index):
    p = gold
    r = p.pct_change(fill_method=None)
    vol = r.rolling(40).std() * np.sqrt(252)
    ma = p.rolling(spec.horizon).mean()
    tr = hysteresis(p, spec.horizon)
    dd = p / p.rolling(spec.horizon).max() - 1
    if spec.family in ("channel", "legacy_channel"):
        upper = p.rolling(spec.horizon).max().shift(1)
        lower = p.rolling(spec.exit_days).min().shift(1)
        on = False
        states = []
        for v, hi, lo in zip(p, upper, lower):
            if v >= hi: on = True
            elif v <= lo: on = False
            states.append(float(on))
        raw = pd.Series(states, index=p.index) * spec.cap
    elif spec.family in ("trend_trail", "vol_trend"):
        raw = tr * spec.cap
        if spec.family == "vol_trend":
            raw = raw * (spec.vol_target / vol).clip(.2, 1)
    elif spec.family == "ensemble":
        raw = (hysteresis(p, max(20, spec.horizon//2)) + tr + hysteresis(p, spec.horizon*2)) / 3 * spec.cap
    elif spec.family == "dual_momentum":
        raw = ((p.pct_change(spec.horizon)>0).astype(float) + (p.pct_change(spec.horizon*2)>0).astype(float)) / 2 * spec.cap
        raw *= (spec.vol_target / vol).clip(.2, 1)
    elif spec.family == "pullback":
        # Trend participates at half cap; buy the pullback, never average down outside trend.
        raw = tr * np.where(p < ma * 1.03, spec.cap, spec.cap * .5)
    elif spec.family == "legacy_momentum":
        raw = pd.Series(np.where(p.pct_change(252)>0, spec.cap*(.14/(r.rolling(60).std()*np.sqrt(252))).clip(.25,1), 0), index=p.index)
    elif spec.family == "legacy_macro":
        cols = []
        for path, col in [("market/yahoo_dollar_index.csv", "close"), ("macro/fred_us_10y_real_yield.csv", "value"), ("macro/fred_vix_close.csv", "value")]:
            s = read_series(ROOT / "data/raw" / path, col)
            # Conservative one-observation delay avoids same-day US release assumptions.
            cols.append(s.shift(1).reindex(p.index, method="ffill").ffill())
        votes = (cols[0].pct_change(60)<0).astype(int)+(cols[1].diff(60)<0).astype(int)+(cols[2].pct_change(10)<=.30).astype(int)
        raw = hysteresis(p,90,.04)*(votes>=1)*spec.cap
    elif spec.family == "hold":
        raw = pd.Series(spec.cap, index=p.index)
    else:
        raise ValueError(spec.family)
    raw = (raw.fillna(0)/.05).round()*.05
    if spec.family.startswith("legacy"):
        # Historical month-end calendar from public observation dates. Exclude
        # current incomplete month, so the last available day cannot masquerade as month-end.
        complete = raw[raw.index.to_period("M") < pd.Timestamp(END).to_period("M")]
        last = complete.groupby(complete.index.to_period("M")).tail(1)
        s = last.reindex(raw.index).ffill().fillna(0.)
        positions=s.index.searchsorted(product_index,side="left")-1
        return np.array([s.iloc[j] if j>=0 else 0. for j in positions])
    if spec.family.startswith("legacy") or spec.family == "hold":
        risk = pd.Series(False, index=p.index)
    else:
        risk = dd < -spec.stop
    # Signals evaluated after the dated London/FX close. Orders use only dates < execution.
    # Monthly reviews: first observed session of month; weekly: first observed session of week.
    keys = p.index.to_period("M" if spec.frequency == "monthly" else "W-FRI")
    review = np.r_[True, keys[1:] != keys[:-1]]
    if spec.family == "hold": review[:] = False; review[0] = True
    target = 0.
    blocked_until = -1
    values = []
    for i, (v, danger) in enumerate(zip(raw.to_numpy(), risk.to_numpy())):
        if danger:
            target = 0.
            blocked_until = i + spec.cooldown
        elif review[i] and i >= blocked_until:
            target = float(v)
        values.append(target)
    s = pd.Series(values, index=p.index)
    positions = s.index.searchsorted(product_index, side="left")-1
    return np.array([s.iloc[j] if j>=0 else 0 for j in positions])


@dataclass(frozen=True)
class Rules:
    # Alipay rule snapshot supplied on 2026-09-08: 0.15% front-end fee
    # under CNY 1m and redemption proceeds credited to Yu'e Bao on T+1.
    buy_fee: float = .0015
    settle_days: int = 1
    cmb_halfspread: float = 2.5
    slippage: float = 0.
    delay: int = 0
    confirmation_delay: int = 1
    redeem_after_confirmation: int = 1
    rebalance: bool = True


def redemption_rate(age):
    return .015 if age < 7 else .005 if age < 30 else 0.


def simulate(frame, signal, path, spec, rules=Rules(), detail=False):
    """Amount orders / share redemptions fixed BEFORE knowing execution price.

    Each closing asset value is cash + unsettled receivables + actual units*price.
    No free rebalancing. Fees deducted from money, FIFO from confirmed lots.
    """
    f = frame.loc[START:].copy()
    indices = frame.index.get_indexer(f.index)
    sig = np.asarray(signal)[indices]
    if rules.delay:
        sig = np.r_[np.repeat(sig[0],rules.delay),sig[:-rules.delay]]
    price_all = frame["nav" if path=="fund" else "cmb_mid"].to_numpy(float)
    prices = f["nav" if path=="fund" else "cmb_mid"].to_numpy(float)
    ordinals = np.array([d.toordinal() for d in frame.index])
    days = ordinals[indices]
    buyable = f["fund_buy" if path=="fund" else "cmb_trade"].to_numpy(bool)
    sellable = f["fund_sell" if path=="fund" else "cmb_trade"].to_numpy(bool)
    cash = INITIAL
    lots = []  # [confirmed index in full product calendar, units, confirmation calendar ordinal]
    receivables = []  # [release index, cash]
    units = 0.
    eqs = []; weights=[]; fees=[]; traded=[]; logs=[]; rows=[]
    last_target = -1.
    equity_previous = INITIAL
    for i, (g, dt, price, target) in enumerate(zip(indices, f.index, prices, sig)):
        for release, amount in receivables:
            if release <= g: cash += amount
        receivables = [(release, amount) for release, amount in receivables if release > g]
        unsettled = sum(a for _,a in receivables)
        previous_price = price_all[g-1] if g>0 else price
        # Fund prior NAV only; fresh execution-day NAV is never used to size orders.
        before_known = cash+unsettled+units*previous_price
        current_known = units*previous_price/before_known
        delta = target*before_known-units*previous_price
        changed = abs(target-last_target)>1e-8
        trade = changed or (rules.rebalance and abs(current_known-target)>=spec.band)
        fee = 0.
        executed = False
        if trade and delta>1 and buyable[i]:
            purchase = min(cash, delta*(1+rules.buy_fee) if path=="fund" else delta)
            purchase = math.floor((purchase+1e-8)*100)/100
            min_order = 1. if path=="fund" else max(1000., previous_price)
            if purchase >= min_order:
                if path=="fund":
                    net = purchase/(1+rules.buy_fee)
                    bought = math.floor((net/price+1e-9)*100)/100
                    fee = purchase-net
                    # Sub-cent unit rounding residual is refunded; all cash reconciles.
                    spent = bought*price+fee
                    confirmation = g+rules.confirmation_delay
                else:
                    ask = price+rules.cmb_halfspread+price*rules.slippage
                    bought = math.floor((purchase/ask+1e-9)*10000)/10000
                    spent = bought*ask
                    fee = bought*(ask-price)
                    confirmation = g
                if bought>0:
                    executed = True
                    conf_day = ordinals[min(confirmation,len(ordinals)-1)]
                    lots.append([confirmation,bought,conf_day])
                    units += bought; cash -= spent
                    if detail: logs.append(dict(date=str(dt.date()),side="buy",units=bought,price=price,cash_amount=spent,fee=fee,target=target,information_cutoff_exclusive=str(dt.date())))
        elif trade and delta < -1 and sellable[i]:
            requested = min(units, -delta/previous_price)
            decimals = 100 if path=="fund" else 10000
            requested = math.floor((requested+1e-8)*decimals)/decimals
            if target<=0: requested = units
            if requested >= (1 if path=="fund" else 1.) or target<=0:
                sold=0.; cost=0.; young=0.
                sell_conf_day = ordinals[min(g+rules.confirmation_delay,len(ordinals)-1)]
                for lot in lots:
                    if lot[0]+(rules.redeem_after_confirmation if path=="fund" else 0)>g: continue
                    take = min(lot[1],requested-sold)
                    if take <= 1e-9: break
                    if path=="fund":
                        age = sell_conf_day-lot[2]
                        cost += take*price*redemption_rate(age)
                        if age<30: young += take
                    else:
                        cost += take*(rules.cmb_halfspread+price*rules.slippage)
                    lot[1]-=take; sold+=take
                if sold>1e-9:
                    executed = True
                    units=max(0.,units-sold); fee=cost; amount=sold*price-fee
                    if path=="fund": receivables.append((g+rules.settle_days,amount))
                    else: cash+=amount
                    lots=[lot for lot in lots if lot[1]>1e-8]
                    if detail: logs.append(dict(date=str(dt.date()),side="sell",units=sold,price=price,cash_amount=amount,fee=fee,target=target,under30_units=young))
        # Retry unavailable/partially funded targets on subsequent sessions.
        after_known = cash+sum(a for _,a in receivables)+units*previous_price
        gap = abs(units*previous_price/after_known-target)
        if trade and gap<max(spec.band,.02): last_target=target
        equity = cash+sum(a for _,a in receivables)+units*price
        weight = units*price/equity
        assert cash>=-1e-5 and units>=-1e-5 and 0<=weight<=1.000001
        assert abs(units-sum(x[1] for x in lots))<1e-5
        eqs.append(equity); weights.append(weight); fees.append(fee); traded.append(executed)
        if detail:
            rows.append(dict(date=str(dt.date()),equity=equity,cash=cash,unsettled=sum(a for _,a in receivables),units=units,price=price,weight=weight,target=target,fee=fee,traded=executed,daily_return=equity/equity_previous-1))
        equity_previous=equity
    det=pd.DataFrame({"equity":eqs,"weight":weights,"fee":fees,"traded":traded},index=f.index)
    return det, logs, rows


def metrics(det, start=START, end=END):
    s=det.loc[start:end]
    earlier=det.loc[det.index<pd.Timestamp(start)]
    base=float(earlier.equity.iloc[-1]) if len(earlier) else INITIAL
    if len(s)==0: return {}
    values=np.r_[base,s.equity.to_numpy()]
    draw=values/np.maximum.accumulate(values)-1
    years=(s.index[-1]-pd.Timestamp(start)).days/365.25
    growth=values[-1]/base
    return {"return_pct":(growth-1)*100,"cagr_pct":(growth**(1/max(years,1/365.25))-1)*100,
            "max_drawdown_pct":float(draw.min()*100),"average_weight_pct":float(s.weight.mean()*100),
            "max_weight_pct":float(s.weight.max()*100),"final_cny":float(values[-1]),
            "fees_cny":float(s.fee.sum()),"trade_days":int(s.traded.sum())}


def load_inputs():
    gold=read_series(INPUT / "gold.csv", "gold_usd")
    frame=pd.read_csv(INPUT / "products.csv",parse_dates=["date"]).set_index("date")
    return gold,frame


def evaluate(spec, gold, frame, rules=Rules(), details=False):
    signal=make_signal(spec,gold,frame.index)
    results={}; output={}
    for path in ["cmb","fund"]:
        det,logs,rows=simulate(frame,signal,path,spec,rules,details)
        results[path]={"full":metrics(det), "splits":{label:metrics(det,a,b) for label,a,b in SPLITS},
                       "years":{str(y):metrics(det,max(f"{y}-01-01",START),min(f"{y}-12-31",END)) for y in range(2021,2027)}}
        if details: output[path]={"trades":logs,"daily":rows}
    return results,output


def feasible(result, stages=2):
    return all(m["max_drawdown_pct"]> -15 and m["average_weight_pct"]<=70
               for p in result.values() for m in list(p["splits"].values())[:stages])


def select():
    gold,frame=load_inputs()
    specs=registry()
    (OUT/"registry.json").write_text(json.dumps([asdict(s) for s in specs],indent=2),encoding="utf-8")
    rows=[]
    # Physically slice away evaluation-period prices during selection.
    train_gold=gold.loc[:"2024-12-31"]; train_frame=frame.loc[:"2024-12-31"]
    for i,spec in enumerate(specs):
        res,_=evaluate(spec,train_gold,train_frame)
        if feasible(res):
            # Maximize the weaker product's 2021-24 annualized return.
            score=min((p["splits"]["2021—2023"]["return_pct"]/100+1)*(p["splits"]["2024"]["return_pct"]/100+1) for p in res.values())**.25-1
        else: score=-999
        rows.append({"id":i,"spec":asdict(spec),"eligible_pre2025":feasible(res),"score":score,"pre2025":res})
        if (i+1)%48==0: print(f"evaluated {i+1}/{len(specs)}",flush=True)
    chosen=[]
    for family in dict.fromkeys(s.family for s in specs):
        eligible=[r for r in rows if r["spec"]["family"]==family and r["eligible_pre2025"]]
        if eligible: chosen.append(max(eligible,key=lambda r:r["score"]))
    chosen.sort(key=lambda r:r["score"],reverse=True)
    (OUT/"selection_pre2025.json").write_text(json.dumps({"selection":"Worst-product CAGR on 2021-24 only; one frozen winner per family", "candidates":rows,"frozen":chosen},ensure_ascii=False,indent=2),encoding="utf-8")
    print("Frozen:",[(r["id"],r["spec"],r["score"]) for r in chosen],flush=True)


def validate():
    gold,frame=load_inputs()
    selected=json.loads((OUT/"selection_pre2025.json").read_text(encoding="utf-8"))["frozen"]
    reports=[]
    for row in selected:
        spec=Spec(**row["spec"])
        result,details=evaluate(spec,gold,frame,details=True)
        reports.append({"id":row["id"],"spec":asdict(spec),"rank_pre2025":len(reports)+1,"eligible_all_stages":feasible(result,3),"results":result})
        (OUT/f"ledger_{row['id']}.json").write_text(json.dumps(details,ensure_ascii=False),encoding="utf-8")
    baselines=[]
    for spec in [Spec("legacy_channel",horizon=60,exit_days=60,cap=.55,frequency="monthly",band=1),
                 Spec("legacy_momentum",cap=.60,frequency="monthly",band=1),
                 Spec("legacy_macro",cap=.60,frequency="monthly",band=1),
                 Spec("hold",cap=1,band=1),Spec("hold",cap=.60,band=1)]:
        result,_=evaluate(spec,gold,frame,rules=Rules(rebalance=False))
        baselines.append({"spec":asdict(spec),"eligible_all_stages":feasible(result,3),"results":result})
    # Keep frozen pre2025 ordering, veto violations only; no ranking on 2025+ returns.
    eligible=[r for r in reports if r["eligible_all_stages"]]
    for r in eligible[:3]:
        spec=Spec(**r["spec"])
        stress={}
        for name,rule in {"fund_standard_fee":Rules(buy_fee=.015),
                          "fund_t7_settlement":Rules(settle_days=7),
                          "extra_one_session_delay":Rules(delay=1),
                          "cmb_double_spread":Rules(cmb_halfspread=5),
                          "combined_cost_delay":Rules(cmb_halfspread=5,slippage=.001,delay=1),
                          "fund_bank_card_t3":Rules(settle_days=3)}.items():
            res,_=evaluate(spec,gold,frame,rule)
            stress[name]={"eligible_all_stages":feasible(res,3),"results":res}
        r["stress"]=stress
    neighbors=[]
    if eligible:
        fixed=Spec(**eligible[0]["spec"])
        for field,values in {"horizon":[108,132],"cap":[.80,.90],"stop":[.108,.132],"vol_target":[.108,.132]}.items():
            for value in values:
                res,_=evaluate(replace(fixed,**{field:value}),gold,frame)
                neighbors.append({"field":field,"value":value,"eligible_all_stages":feasible(res,3),"results":res})
    output={"initial_per_product":INITIAL,"start":START,"end":END,"rules":asdict(Rules()),
            "candidates":reports,"baselines":baselines,"selected_ids":[r["id"] for r in eligible[:3]],
            "primary_id":eligible[0]["id"] if eligible else None,"primary_parameter_sensitivity":neighbors,
            "limitations":["CMB historical executable quotes unavailable; London x FX mid-price proxy, fixed 5 CNY/g current-spread scenario, not literal historical fills.",
                           "Alipay discount not verified. Base uses 1.5% standard purchase fee; 0.15% sensitivity only.",
            "Fund base assumptions match the supplied Alipay screenshot: 0.15% subscription fee below CNY 1m and Yu'e Bao settlement on T+1. Bank-card settlement is a separate T+3 scenario.",
                           "Fund T+1 confirmation, earliest redemption next session (T+2), a conservative channel-availability assumption.",
                           "New monthly reviews use first observed London session. Legacy baselines retain original month-end signals (except last incomplete month); macro features delayed one source observation.",
                           "Old research has already seen 2025+; this is chronological validation, not untouched out-of-sample proof.",
                           "Mean weights measured at every available China NAV close per stage; intraday drawdowns unavailable.",
                           "CMB min order 1 gram/1000 CNY and 0.0001g precision are conservative modeling assumptions, not verified full-history limits."]}
    (OUT/"result.json").write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"selected_ids":output["selected_ids"],"candidates":[{"id":r["id"],"spec":r["spec"],"ok":r["eligible_all_stages"],"full":{p:v["full"] for p,v in r["results"].items()}} for r in reports],"baseline":[{"family":b["spec"]["family"],"cap":b["spec"]["cap"],"ok":b["eligible_all_stages"],"full":{p:v["full"] for p,v in b["results"].items()}} for b in baselines]},ensure_ascii=False,indent=2))


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("command",choices=["prepare","select","validate"])
    args=parser.parse_args()
    {"prepare":prepare,"select":select,"validate":validate}[args.command]()
