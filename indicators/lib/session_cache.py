"""
Session cache: avoids recalculating the same indicator twice
during a backtesting session (including optimization runs).

Key = (symbol, timeframe, indicator_name, version, params_hash, data_range_hash)
Value = numpy array of computed values

Cache is created per session and garbage collected when session ends.
"""

import hashlib
import numpy as np
from typing import Dict, Tuple, Optional


class SessionCache:
    def __init__(self):
        self._cache: Dict[str, np.ndarray] = {}
        self._hits = 0
        self._misses = 0

    def _make_key(self, symbol: str, timeframe: str, indicator_name: str,
                  version: str, params_hash: str, data_len: int) -> str:
        raw = f"{symbol}|{timeframe}|{indicator_name}|{version}|{params_hash}|{data_len}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, symbol: str, timeframe: str, indicator_name: str,
            version: str, params_hash: str, data_len: int) -> Optional[np.ndarray]:
        key = self._make_key(symbol, timeframe, indicator_name, version, params_hash, data_len)
        result = self._cache.get(key)
        if result is not None:
            self._hits += 1
        else:
            self._misses += 1
        return result

    def put(self, symbol: str, timeframe: str, indicator_name: str,
            version: str, params_hash: str, data_len: int,
            values: np.ndarray):
        key = self._make_key(symbol, timeframe, indicator_name, version, params_hash, data_len)
        self._cache[key] = values

    def clear(self):
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    @property
    def stats(self):
        return {
            "entries": len(self._cache),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self._hits / max(1, self._hits + self._misses) * 100, 1),
        }
