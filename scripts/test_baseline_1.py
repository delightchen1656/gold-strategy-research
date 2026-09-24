"""Economic and causality checks for the cash/share engine."""
import json
import unittest
import numpy as np
import pandas as pd
from baseline_1_engine import (INITIAL, OUT, START, Spec, Rules, load_inputs,
                                  make_signal, simulate, redemption_rate, metrics)
from run_baseline_1 import overlay_signal


def fixture(prices):
    dates=pd.bdate_range("2020-12-31",periods=len(prices))
    return pd.DataFrame({"nav":prices,"cmb_mid":np.array(prices)*100,
                         "fund_buy":True,"fund_sell":True,"cmb_trade":True},index=dates)


class EconomicTests(unittest.TestCase):
    def test_passive_units_drift_not_free_rebalance(self):
        f=fixture([1.,1.,1.,2.,2.])
        d,t,_=simulate(f,np.full(len(f),.5),"fund",Spec("hold",band=1),Rules(buy_fee=0,rebalance=False),True)
        self.assertAlmostEqual(d.equity.iloc[-1],75000,places=5)
        self.assertAlmostEqual(d.weight.iloc[-1],2/3,places=5)
        self.assertEqual(len(t),1)

    def test_purchase_fee_external_calculation(self):
        f=fixture([1.]*6)
        rules=Rules()
        d,t,_=simulate(f,np.ones(len(f)),"fund",Spec("hold",band=1),rules,True)
        self.assertAlmostEqual(t[0]["fee"],50000-50000/(1+rules.buy_fee),places=7)
        self.assertAlmostEqual(d.equity.iloc[-1],50000-t[0]["fee"],places=6)

    def test_fifo_fee_boundaries(self):
        self.assertEqual([redemption_rate(x) for x in [0,6,7,29,30,365]], [.015,.015,.005,.005,0,0])

    def test_unsettled_proceeds_cannot_be_reinvested(self):
        f=fixture([1.]*20)
        signals=np.ones(len(f)); signals[3:5]=0
        rules=Rules(buy_fee=0,settle_days=7)
        d,t,rows=simulate(f,signals,"fund",Spec("hold",band=.01),rules,True)
        buys=[r for r in t if r["side"]=="buy"]
        sell=next(r for r in t if r["side"]=="sell")
        g=f.index.get_loc(sell["date"])
        self.assertGreaterEqual(pd.Timestamp(buys[1]["date"]),f.index[g+rules.settle_days])
        self.assertAlmostEqual(sell["fee"],750.,places=5)
        self.assertTrue(any(r["unsettled"]>0 and r["cash"]<1 for r in rows))

    def test_orders_do_not_know_execution_nav(self):
        f=fixture([1.]*10); signal=np.zeros(len(f)); signal[3:]=.5
        _,a,_=simulate(f,signal,"fund",Spec("hold",band=1),Rules(buy_fee=0),True)
        f2=f.copy(); f2.loc[f2.index[3],"nav"]=2
        _,b,_=simulate(f2,signal,"fund",Spec("hold",band=1),Rules(buy_fee=0),True)
        self.assertAlmostEqual(a[0]["cash_amount"],b[0]["cash_amount"],places=5)
        self.assertAlmostEqual(a[0]["units"],2*b[0]["units"],places=5)

    def test_daily_cash_shares_reconcile(self):
        gold,f=load_inputs(); spec=Spec("vol_trend",horizon=120,cap=.85,stop=.12,frequency="monthly")
        signal=make_signal(spec,gold,f.index)
        for path in ["fund","cmb"]:
            d,trades,rows=simulate(f,signal,path,spec,detail=True)
            for r in rows:
                self.assertAlmostEqual(r["equity"],r["cash"]+r["unsettled"]+r["units"]*r["price"],places=6)
            unit_sum=0.; cash_and_due=INITIAL
            for t in trades:
                if t["side"]=="buy": unit_sum+=t["units"]; cash_and_due-=t["cash_amount"]
                else: unit_sum-=t["units"]; cash_and_due+=t["cash_amount"]
            self.assertAlmostEqual(unit_sum,rows[-1]["units"],places=5)
            self.assertAlmostEqual(cash_and_due,rows[-1]["cash"]+rows[-1]["unsettled"],places=5)
            stages=[metrics(d,a,b)["return_pct"] for a,b in [(START,"2023-12-31"),("2024-01-01","2024-12-31"),("2025-01-01","2026-09-04")]]
            self.assertAlmostEqual(np.prod(1+np.array(stages)/100)-1,d.equity.iloc[-1]/INITIAL-1,places=10)
            self.assertEqual(sum(d.traded),len(trades))

    def test_future_price_changes_do_not_change_previous_signals(self):
        gold,f=load_inputs()
        for family in ["channel","trend_trail","ensemble","dual_momentum","vol_trend","pullback"]:
            spec=Spec(family,horizon=120,cap=.85,stop=.12,frequency="monthly")
            original=make_signal(spec,gold,f.index)
            for cutoff in ["2023-06-15","2024-12-31","2026-01-30"]:
                idx=f.index[f.index<=cutoff]
                truncated=make_signal(spec,gold.loc[:cutoff],idx)
                np.testing.assert_allclose(original[:len(idx)],truncated,atol=0,rtol=0)

    def test_same_day_london_fix_cannot_affect_same_day_fund_order(self):
        dates=pd.bdate_range("2024-01-02",periods=180)
        gold=pd.Series(np.linspace(1800,2200,len(dates)),index=dates)
        execution_day=dates[150]
        changed=gold.copy()
        changed.loc[execution_day]=5000
        spec=Spec("vol_trend",horizon=120,cap=1,vol_target=.12,stop=.14,
                  frequency="monthly",band=.05,cooldown=5)
        original=make_signal(spec,gold,dates)
        revised=make_signal(spec,changed,dates)
        self.assertEqual(original[150],revised[150])
        original_overlay=overlay_signal(gold,dates)
        revised_overlay=overlay_signal(changed,dates)
        self.assertEqual(original_overlay[150],revised_overlay[150])


if __name__=="__main__":
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(EconomicTests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    (OUT/"test_results.json").write_text(json.dumps({"tests":result.testsRun,"failures":len(result.failures),"errors":len(result.errors),"success":result.wasSuccessful()},indent=2),encoding="utf-8")
    raise SystemExit(0 if result.wasSuccessful() else 1)
