"""
Base class for indicator plugins.
All indicators must implement this interface.
Functions are PURE: same input + same params = same output. Always.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any
import numpy as np


class IndicatorPlugin(ABC):
    """Base class for all indicator plugins."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier, e.g. 'ema', 'rsi', 'sar'."""
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """Semantic version, e.g. 'v1.0'. Bump on ANY logic change."""
        pass

    @property
    @abstractmethod
    def category(self) -> str:
        """'trend', 'oscillator', 'volume', 'volatility'."""
        pass

    @property
    @abstractmethod
    def default_params(self) -> Dict[str, Any]:
        """Default parameters, e.g. {'period': 14}."""
        pass

    @abstractmethod
    def compute(self, closes: np.ndarray, highs: np.ndarray,
                lows: np.ndarray, volumes: np.ndarray,
                params: Dict[str, Any]) -> np.ndarray:
        """
        Pure function: compute indicator values.
        Input arrays are all the same length.
        Returns np.ndarray of same length (NaN where not enough data).
        """
        pass

    def params_hash(self, params: Dict[str, Any]) -> str:
        """Deterministic hash of params for caching."""
        import hashlib
        import json
        raw = json.dumps(params, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()[:12]
