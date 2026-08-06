"""Backend adapters for external systems."""

from opspilot.tools.adapters.git import GitAdapter
from opspilot.tools.adapters.loki import LokiAdapter
from opspilot.tools.adapters.prometheus import PrometheusAdapter
from opspilot.tools.adapters.simulator_api import SimulatorApiAdapter

__all__ = [
    "GitAdapter",
    "LokiAdapter",
    "PrometheusAdapter",
    "SimulatorApiAdapter",
]
