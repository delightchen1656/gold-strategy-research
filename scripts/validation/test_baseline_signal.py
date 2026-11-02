"""Causality checks for the frozen Baseline 1 signal."""

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.core.baseline_signal import generate_baseline_signal


CONFIG = {
    "slow": 120,
    "fast": 20,
    "buffer": 0.02,
    "exit_buffer": 0.02,
    "breakout": 90,
    "entry_mode": "either",
    "stop": 0.08,
    "cooldown": 5,
    "reentry_filter": "none",
}


def frame(close):
    values = np.asarray(close, dtype=float)
    index = pd.date_range("2020-01-01", periods=len(values), freq="D")
    return pd.DataFrame(
        {"open": values, "high": values, "low": values, "close": values},
        index=index,
    )


class BaselineSignalTests(unittest.TestCase):
    def test_future_prices_do_not_change_past_signals(self):
        prices = np.r_[np.linspace(100, 130, 180), np.linspace(130, 105, 80)]
        original = generate_baseline_signal(frame(prices), CONFIG)
        changed = prices.copy()
        changed[220:] *= 3
        revised = generate_baseline_signal(frame(changed), CONFIG)
        np.testing.assert_array_equal(original[:220], revised[:220])

    def test_output_is_long_or_cash(self):
        prices = np.linspace(100, 200, 260)
        signal = generate_baseline_signal(frame(prices), CONFIG)
        self.assertEqual(len(signal), len(prices))
        self.assertTrue(set(np.unique(signal)).issubset({0.0, 1.0}))

    def test_current_close_affects_only_later_execution(self):
        prices = np.linspace(100, 130, 200)
        changed = prices.copy()
        changed[150] = 500
        original = generate_baseline_signal(frame(prices), CONFIG)
        revised = generate_baseline_signal(frame(changed), CONFIG)
        self.assertEqual(original[150], revised[150])


if __name__ == "__main__":
    unittest.main(verbosity=2)
