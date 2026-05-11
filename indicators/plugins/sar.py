"""Parabolic SAR indicator plugin."""

import numpy as np
from typing import Dict, Any
from plugins.base_plugin import IndicatorPlugin


class SARPlugin(IndicatorPlugin):
    name = "sar"
    version = "v1.0"
    category = "trend"
    default_params = {"af_start": 0.02, "af_step": 0.02, "af_max": 0.2}

    def compute(self, closes, highs, lows, volumes, params):
        af_start = params.get("af_start", self.default_params["af_start"])
        af_step = params.get("af_step", self.default_params["af_step"])
        af_max = params.get("af_max", self.default_params["af_max"])

        n = len(highs)
        sar = np.full(n, np.nan)
        if n < 2:
            return sar

        bull = True
        af = af_start
        ep = highs[0]
        sar[0] = lows[0]

        for i in range(1, n):
            prev_sar = sar[i - 1] if not np.isnan(sar[i - 1]) else lows[i - 1]
            sar_val = prev_sar + af * (ep - prev_sar)

            if bull:
                sar_val = min(sar_val, lows[i - 1])
                if i >= 2 and not np.isnan(sar[i - 2]):
                    sar_val = min(sar_val, lows[i - 2])
                if sar_val > lows[i]:
                    bull = False
                    sar_val = ep
                    ep = lows[i]
                    af = af_start
                else:
                    if highs[i] > ep:
                        ep = highs[i]
                        af = min(af + af_step, af_max)
            else:
                sar_val = max(sar_val, highs[i - 1])
                if i >= 2 and not np.isnan(sar[i - 2]):
                    sar_val = max(sar_val, highs[i - 2])
                if sar_val < highs[i]:
                    bull = True
                    sar_val = ep
                    ep = highs[i]
                    af = af_start
                else:
                    if lows[i] < ep:
                        ep = lows[i]
                        af = min(af + af_step, af_max)

            sar[i] = sar_val

        return sar
