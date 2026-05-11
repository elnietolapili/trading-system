"""
Plugin registry: discovers and manages all indicator plugins.
Single source of truth for available indicators.
"""

from typing import Dict, Optional
from plugins.base_plugin import IndicatorPlugin
from plugins.ema import EMAPlugin
from plugins.rsi import RSIPlugin
from plugins.rsi_ma import RSIMAPlugin
from plugins.sar import SARPlugin


class PluginRegistry:
    def __init__(self):
        self._plugins: Dict[str, IndicatorPlugin] = {}
        self._register_defaults()

    def _register_defaults(self):
        for plugin_class in [EMAPlugin, RSIPlugin, RSIMAPlugin, SARPlugin]:
            plugin = plugin_class()
            self._plugins[plugin.name] = plugin

    def register(self, plugin: IndicatorPlugin):
        self._plugins[plugin.name] = plugin

    def get(self, name: str) -> Optional[IndicatorPlugin]:
        return self._plugins.get(name)

    def list_all(self):
        return [
            {
                "name": p.name,
                "version": p.version,
                "category": p.category,
                "default_params": p.default_params,
            }
            for p in self._plugins.values()
        ]

    def list_names(self):
        return list(self._plugins.keys())


# Global singleton
registry = PluginRegistry()
