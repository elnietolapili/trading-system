"""RSI MA (Simple Moving Average of RSI) indicator plugin."""

import numpy as np
from typing import Dict, Any
from plugins.base_plugin import IndicatorPlugin
from plugins.rsi import RSIPlugin


class RSIMAPlugin(IndicatorPlugin):
    name = "rsi_ma"
    version = "v1.0"
    category = "oscillator"
    default_params = {"rsi_period": 14, "ma_period": 14}

    def compute(self, closes, highs, lows, volumes, params):
        rsi_period = params.get("rsi_period", 14)
        ma_period = params.get("ma_period", 14)

        # Calculate RSI first
        rsi_plugin = RSIPlugin()
        rsi = rsi_plugin.compute(closes, highs, lows, volumes, {"period": rsi_period})

        # SMA of RSI
        n = len(rsi)
        result = np.full(n, np.nan)
        valid = ~np.isnan(rsi)
        valid_indices = np.where(valid)[0]

        if len(valid_indices) < ma_period:
            return result

        for i in range(ma_period - 1, len(valid_indices)):
            idx = valid_indices[i]
            window = rsi[valid_indices[i - ma_period + 1]:idx + 1]
            window = window[~np.isnan(window)]
            if len(window) == ma_period:
                result[idx] = np.mean(window)

        return result
