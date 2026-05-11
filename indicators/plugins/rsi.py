"""RSI (Relative Strength Index) indicator plugin."""

import numpy as np
from typing import Dict, Any
from plugins.base_plugin import IndicatorPlugin


class RSIPlugin(IndicatorPlugin):
    name = "rsi"
    version = "v1.0"
    category = "oscillator"
    default_params = {"period": 14}

    def compute(self, closes, highs, lows, volumes, params):
        period = params.get("period", self.default_params["period"])
        n = len(closes)
        rsi = np.full(n, np.nan)
        if n < period + 1:
            return rsi
        deltas = np.diff(closes)
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)
        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])
        if avg_loss == 0:
            rsi[period] = 100.0
        else:
            rsi[period] = 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))
        for i in range(period, len(deltas)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            if avg_loss == 0:
                rsi[i + 1] = 100.0
            else:
                rsi[i + 1] = 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))
        return rsi
