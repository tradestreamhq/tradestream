"""Parameter grid generation via cartesian product."""

import itertools
from typing import Any, Dict, List

from services.param_optimizer.models import ParameterRange


class ParameterGrid:
    """Generates the cartesian product of parameter ranges."""

    def __init__(self, param_ranges: List[ParameterRange]):
        if not param_ranges:
            raise ValueError("At least one ParameterRange is required")
        self._ranges = param_ranges

    @property
    def size(self) -> int:
        """Total number of parameter combinations."""
        total = 1
        for r in self._ranges:
            total *= len(r.values)
        return total

    @property
    def param_names(self) -> List[str]:
        return [r.name for r in self._ranges]

    def generate(self) -> List[Dict[str, Any]]:
        """Return all parameter combinations as a list of dicts."""
        names = [r.name for r in self._ranges]
        value_lists = [r.values for r in self._ranges]
        return [dict(zip(names, combo)) for combo in itertools.product(*value_lists)]
