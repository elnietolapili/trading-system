"""EMA (Exponential Moving Average) indicator plugin."""

import numpy as np
from typing import Dict, Any
from plugins.base_plugin import IndicatorPlugin


class EMAPlugin(IndicatorPlugin):
    name = "ema"
    version = "v1.0"
    category = "trend"
    default_params = {"period": 20}

    def compute(self, closes, highs, lows, volumes, params):
        period = params.get("period", self.default_params["period"])
        n = len(closes)
        ema = np.full(n, np.nan)
        if n < period:
            return ema
        ema[period - 1] = np.mean(closes[:period])
        m = 2.0 / (period + 1)
        for i in range(period, n):
            ema[i] = closes[i] * m + ema[i - 1] * (1 - m)
        return ema
