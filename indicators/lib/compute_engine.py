"""
Compute engine: calculates indicators in memory.
Used as LIBRARY by Strategy Runner (no HTTP, no disk).
Used as backend by the HTTP service for interface/scheduler.

This is the core of Feature Engineering.
"""

import numpy as np
from typing import Dict, Any, List, Optional
from plugin_registry import registry
from lib.session_cache import SessionCache


class ComputeEngine:
    """
    Stateless indicator compute engine.
    Optionally uses a SessionCache for backtesting sessions.
    """

    def __init__(self, cache: Optional[SessionCache] = None):
        self.cache = cache

    def compute_indicator(
        self,
        indicator_name: str,
        params: Dict[str, Any],
        closes: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        volumes: np.ndarray,
        symbol: str = "",
        timeframe: str = "",
    ) -> Optional[np.ndarray]:
        """
        Compute a single indicator. Uses cache if available.
        Returns numpy array or None if indicator not found.
        """
        plugin = registry.get(indicator_name)
        if not plugin:
            return None

        p_hash = plugin.params_hash(params)

        # Check cache
        if self.cache:
            cached = self.cache.get(
                symbol, timeframe, indicator_name,
                plugin.version, p_hash, len(closes),
            )
            if cached is not None:
                return cached

        # Compute
        result = plugin.compute(closes, highs, lows, volumes, params)

        # Store in cache
        if self.cache:
            self.cache.put(
                symbol, timeframe, indicator_name,
                plugin.version, p_hash, len(closes), result,
            )

        return result

    def compute_batch(
        self,
        requests: List[Dict[str, Any]],
        closes: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        volumes: np.ndarray,
        symbol: str = "",
        timeframe: str = "",
    ) -> Dict[str, np.ndarray]:
        """
        Compute multiple indicators in one call.
        requests = [{"name": "ema", "params": {"period": 9}}, ...]
        Returns dict: {"ema_9": array, "rsi_14": array, ...}
        """
        results = {}
        for req in requests:
            name = req["name"]
            params = req.get("params", {})
            key = f"{name}_{self._params_label(params)}"
            result = self.compute_indicator(
                name, params, closes, highs, lows, volumes, symbol, timeframe,
            )
            if result is not None:
                results[key] = result
        return results

    def get_indicator_metadata(self, indicator_name: str, params: Dict[str, Any]):
        """Return metadata about an indicator computation."""
        plugin = registry.get(indicator_name)
        if not plugin:
            return None
        return {
            "name": plugin.name,
            "version": plugin.version,
            "category": plugin.category,
            "params": params,
            "params_hash": plugin.params_hash(params),
        }

    def _params_label(self, params: Dict[str, Any]) -> str:
        """Human-readable label from params, e.g. '9' or '0.015_0.015_0.12'."""
        if not params:
            return "default"
        vals = [str(v) for v in params.values()]
        return "_".join(vals)
