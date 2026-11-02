"""Frozen signal implementation shared by the active Baseline 1 workflow.

This module contains only the registered production rule. Parameter searches and
alternative signal families belong to archived research, not the active code.
"""

import numpy as np


def generate_baseline_signal(frame, config):
    """Return causal long/cash weights for the frozen MA-plus-breakout rule."""
    close = frame.close
    slow = close.rolling(config["slow"]).mean()
    fast = close.rolling(config["fast"]).mean()
    trend = fast > slow * (1 + config["buffer"])
    breakout = (
        (close > close.rolling(config["breakout"]).max().shift())
        & (close > slow)
    )
    mode = config["entry_mode"]
    entry = trend | breakout if mode == "either" else (
        trend & breakout if mode == "both" else breakout
    )
    if config["reentry_filter"] == "ma20":
        entry &= close > fast
    elif config["reentry_filter"] == "rising_ma20":
        entry &= (close > fast) & (fast > fast.shift(5))

    leave = (fast < slow * (1 - config["exit_buffer"])).to_numpy()
    entry = entry.to_numpy()
    on = False
    peak = 0.0
    blocked_until = -1
    result = []
    for index, price in enumerate(close):
        if on:
            peak = max(peak, price)
            if leave[index] or price < peak * (1 - config["stop"]):
                on = False
                blocked_until = index + config["cooldown"]
        elif index >= blocked_until and entry[index]:
            on = True
            peak = price
        result.append(float(on))
    return np.r_[0.0, result[:-1]]
