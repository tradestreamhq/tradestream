"""Agent state persistence — tracks cycle history, candidates, and promotions."""

import json
import os
import time

from absl import logging

from services.agent_orchestration import config


class CandidateRecord:
    """A strategy candidate tracked through the orchestration pipeline."""

    def __init__(
        self,
        name,
        spec,
        phase=config.PHASE_DISCOVERY,
        created_at=None,
        metrics=None,
        allocation_weight=0.0,
    ):
        self.name = name
        self.spec = spec
        self.phase = phase
        self.created_at = created_at or time.time()
        self.metrics = metrics or {}
        self.allocation_weight = allocation_weight

    def to_dict(self):
        return {
            "name": self.name,
            "spec": self.spec,
            "phase": self.phase,
            "created_at": self.created_at,
            "metrics": self.metrics,
            "allocation_weight": self.allocation_weight,
        }

    @classmethod
    def from_dict(cls, d):
        return cls(
            name=d["name"],
            spec=d["spec"],
            phase=d.get("phase", config.PHASE_DISCOVERY),
            created_at=d.get("created_at", 0),
            metrics=d.get("metrics", {}),
            allocation_weight=d.get("allocation_weight", 0.0),
        )


class OrchestrationState:
    """Persistent state for the orchestration agent.

    Tracks:
    - Current cycle number
    - Candidates in each phase (discovery, validation, promotion, live)
    - Promotion history
    - Retirement history
    """

    def __init__(self, state_file=None):
        self.state_file = state_file or config.STATE_FILE_DEFAULT
        self.cycle_number = 0
        self.last_cycle_time = 0
        self.candidates = {}  # name -> CandidateRecord
        self.promotion_history = []  # list of {name, promoted_at, cycle}
        self.retirement_history = []  # list of {name, retired_at, cycle, reason}
        self.cycle_stats = []  # list of per-cycle stats

    def load(self):
        """Load state from disk."""
        if not os.path.exists(self.state_file):
            logging.info(
                "No existing state file at %s, starting fresh.", self.state_file
            )
            return
        try:
            with open(self.state_file, "r") as f:
                data = json.load(f)
            self.cycle_number = data.get("cycle_number", 0)
            self.last_cycle_time = data.get("last_cycle_time", 0)
            self.candidates = {
                name: CandidateRecord.from_dict(rec)
                for name, rec in data.get("candidates", {}).items()
            }
            self.promotion_history = data.get("promotion_history", [])
            self.retirement_history = data.get("retirement_history", [])
            self.cycle_stats = data.get("cycle_stats", [])
            logging.info(
                "Loaded state: cycle=%d, candidates=%d, promoted=%d, retired=%d",
                self.cycle_number,
                len(self.candidates),
                len(self.promotion_history),
                len(self.retirement_history),
            )
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logging.error("Failed to load state from %s: %s", self.state_file, e)

    def save(self):
        """Persist state to disk."""
        data = {
            "cycle_number": self.cycle_number,
            "last_cycle_time": self.last_cycle_time,
            "candidates": {
                name: rec.to_dict() for name, rec in self.candidates.items()
            },
            "promotion_history": self.promotion_history,
            "retirement_history": self.retirement_history,
            "cycle_stats": self.cycle_stats[-100:],  # Keep last 100 cycles
        }
        tmp_path = self.state_file + ".tmp"
        try:
            os.makedirs(os.path.dirname(self.state_file) or ".", exist_ok=True)
            with open(tmp_path, "w") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_path, self.state_file)
        except OSError as e:
            logging.error("Failed to save state to %s: %s", self.state_file, e)

    def add_candidate(self, name, spec):
        """Add a new discovery candidate."""
        self.candidates[name] = CandidateRecord(name=name, spec=spec)

    def advance_to_validation(self, name, metrics):
        """Move candidate to validation phase with backtest metrics."""
        if name in self.candidates:
            self.candidates[name].phase = config.PHASE_VALIDATION
            self.candidates[name].metrics = metrics

    def promote(self, name, allocation_weight):
        """Promote a validated candidate to the live signal pipeline."""
        if name in self.candidates:
            self.candidates[name].phase = config.PHASE_PROMOTION
            self.candidates[name].allocation_weight = allocation_weight
            self.promotion_history.append(
                {
                    "name": name,
                    "promoted_at": time.time(),
                    "cycle": self.cycle_number,
                }
            )

    def retire(self, name, reason):
        """Retire a promoted strategy."""
        if name in self.candidates:
            self.retirement_history.append(
                {
                    "name": name,
                    "retired_at": time.time(),
                    "cycle": self.cycle_number,
                    "reason": reason,
                }
            )
            del self.candidates[name]

    def get_candidates_in_phase(self, phase):
        """Get all candidates in a given phase."""
        return [c for c in self.candidates.values() if c.phase == phase]

    def get_promoted_strategies(self):
        """Get all currently promoted (live) strategies."""
        return self.get_candidates_in_phase(config.PHASE_PROMOTION)

    def record_cycle_stats(self, stats):
        """Record stats for the current cycle."""
        stats["cycle"] = self.cycle_number
        stats["timestamp"] = time.time()
        self.cycle_stats.append(stats)
