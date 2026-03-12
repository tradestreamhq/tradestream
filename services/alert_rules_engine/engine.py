"""Alert rules evaluation engine.

Periodically fetches market/portfolio state and evaluates all enabled rules,
firing actions and recording events when conditions are met.
"""

import time
from dataclasses import asdict

import requests

from services.alert_rules_engine.actions import dispatch_action
from services.alert_rules_engine.conditions import evaluate_condition
from services.alert_rules_engine.models import AlertEvent, AlertRule
from services.alert_rules_engine.rule_store import RuleStore
from services.shared.structured_logger import StructuredLogger

_log = StructuredLogger(service_name="alert_rules_engine")


class AlertEngine:
    """Evaluates alert rules against current market and portfolio state."""

    def __init__(
        self,
        rule_store: RuleStore,
        portfolio_url: str = "http://localhost:8095",
        market_data_url: str = "http://localhost:8081",
    ):
        self.rule_store = rule_store
        self.portfolio_url = portfolio_url.rstrip("/")
        self.market_data_url = market_data_url.rstrip("/")
        self._last_signal: dict | None = None
        self._last_regime: dict | None = None

    def set_signal(self, signal_data: dict) -> None:
        """Update the latest signal for evaluation."""
        self._last_signal = signal_data

    def set_regime(self, regime_data: dict) -> None:
        """Update the latest regime data for evaluation."""
        self._last_regime = regime_data

    def fetch_portfolio_data(self) -> dict:
        """Fetch current portfolio risk metrics."""
        try:
            resp = requests.get(f"{self.portfolio_url}/portfolio/risk", timeout=5)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            _log.warning("Failed to fetch portfolio data", error=str(e))
        return {}

    def fetch_market_data(self, symbols: list[str]) -> dict:
        """Fetch current prices for the given symbols.

        Returns a dict keyed by symbol with price info.
        """
        result = {}
        for symbol in symbols:
            try:
                resp = requests.get(
                    f"{self.market_data_url}/market/price",
                    params={"symbol": symbol},
                    timeout=5,
                )
                if resp.status_code == 200:
                    result[symbol] = resp.json()
            except Exception as e:
                _log.warning("Failed to fetch market data", symbol=symbol, error=str(e))
        return result

    def _collect_symbols(self, rules: list[AlertRule]) -> list[str]:
        """Extract unique symbols referenced by rules."""
        symbols = set()
        for rule in rules:
            symbol = rule.condition.params.get("symbol")
            if symbol:
                symbols.add(symbol)
        return list(symbols)

    def evaluate_all(self) -> list[AlertEvent]:
        """Evaluate all enabled rules and fire matching actions.

        Returns a list of AlertEvent for rules that triggered.
        """
        rules = self.rule_store.list_enabled()
        if not rules:
            return []

        now = time.time()

        # Fetch state
        symbols = self._collect_symbols(rules)
        market_data = self.fetch_market_data(symbols) if symbols else {}
        portfolio_data = self.fetch_portfolio_data()

        events = []
        for rule in rules:
            if rule.is_in_cooldown(now):
                continue

            triggered, message, context = evaluate_condition(
                rule.condition,
                market_data,
                portfolio_data,
                self._last_signal,
                self._last_regime,
            )

            if not triggered:
                continue

            _log.info(
                "Alert triggered",
                rule_id=rule.rule_id,
                rule_name=rule.name,
                message=message,
            )

            # Dispatch action
            success = dispatch_action(
                rule.action.action_type.value,
                rule.action.params,
                message,
                context,
            )

            # Record event
            event = AlertEvent(
                event_id="",
                rule_id=rule.rule_id,
                rule_name=rule.name,
                condition_type=rule.condition.condition_type.value,
                message=message,
                context={**context, "action_success": success},
            )
            self.rule_store.record_event(asdict(event))
            events.append(event)

            # Update cooldown
            self.rule_store.mark_triggered(rule, now)

            # Clear one-shot data after consumption
            if rule.condition.condition_type.value == "signal_match":
                self._last_signal = None
            if rule.condition.condition_type.value == "regime_change":
                self._last_regime = None

        return events

    def run_loop(self, interval_seconds: int = 30, shutdown_flag=None) -> None:
        """Run the evaluation loop until shutdown.

        Args:
            interval_seconds: Seconds between evaluation cycles.
            shutdown_flag: A callable returning True to stop the loop.
        """
        _log.info("Alert engine loop started", interval=interval_seconds)
        while True:
            if shutdown_flag and shutdown_flag():
                break
            try:
                events = self.evaluate_all()
                if events:
                    _log.info("Evaluation cycle complete", alerts_fired=len(events))
            except Exception as e:
                _log.error("Evaluation cycle failed", error=str(e))
            time.sleep(interval_seconds)
        _log.info("Alert engine loop stopped")
