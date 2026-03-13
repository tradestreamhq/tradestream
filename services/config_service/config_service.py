"""
Configuration Management Service for TradeStream.

Manages runtime configuration with validation, hot-reload, and
config inheritance (default -> environment -> user override).
Supports namespaces: exchange, strategy, risk, notification.
"""

import copy
import logging
import os
import re
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

import yaml

from services.config_service.schema import CONFIG_SCHEMA, NAMESPACE_SCHEMAS

logger = logging.getLogger(__name__)

SECRET_PATTERNS = re.compile(
    r"(password|secret|key|token|credential|api_key)", re.IGNORECASE
)
MASK = "********"

VALID_NAMESPACES = {"exchange", "strategy", "risk", "notification"}


class ConfigValidationError(Exception):
    """Raised when config validation fails."""

    def __init__(self, errors: List[Dict[str, str]]):
        self.errors = errors
        super().__init__(f"Config validation failed: {errors}")


class ConfigService:
    """Centralized configuration service with validation and hot-reload."""

    def __init__(
        self,
        config_dir: Optional[str] = None,
        db_pool=None,
    ):
        self._config_dir = Path(config_dir) if config_dir else None
        self._db_pool = db_pool
        self._config: Dict[str, Dict[str, Any]] = {}
        self._defaults: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()
        self._watchers: List[Callable] = []
        self._watch_thread: Optional[threading.Thread] = None
        self._watching = False

        self._load_defaults()

    def _load_defaults(self):
        """Load built-in default configuration."""
        self._defaults = {
            "exchange": {
                "default_exchange": "binance",
                "sandbox_mode": True,
                "rate_limit": 1200,
                "timeout_ms": 30000,
                "retry_count": 3,
            },
            "strategy": {
                "max_concurrent_strategies": 10,
                "evaluation_interval_seconds": 60,
                "default_timeframe": "1h",
                "backtest_days": 90,
            },
            "risk": {
                "max_position_pct": 10.0,
                "stop_loss_pct": 5.0,
                "take_profit_pct": 15.0,
                "max_drawdown_pct": 20.0,
                "max_open_positions": 5,
                "daily_loss_limit_pct": 10.0,
            },
            "notification": {
                "enabled": True,
                "channels": ["log"],
                "min_severity": "info",
                "throttle_seconds": 60,
            },
        }
        with self._lock:
            self._config = copy.deepcopy(self._defaults)

    def load(self):
        """Load config from all sources in priority order:
        defaults -> YAML files -> environment variables -> database.
        """
        with self._lock:
            self._config = copy.deepcopy(self._defaults)
            self._load_from_yaml()
            self._load_from_env()
            self._load_from_db()

    def _load_from_yaml(self):
        """Load config from YAML files in config_dir."""
        if not self._config_dir or not self._config_dir.exists():
            return

        for ns in VALID_NAMESPACES:
            yaml_path = self._config_dir / f"{ns}.yaml"
            if yaml_path.exists():
                try:
                    with open(yaml_path) as f:
                        data = yaml.safe_load(f)
                    if isinstance(data, dict):
                        self._config.setdefault(ns, {}).update(data)
                        logger.info("Loaded config from %s", yaml_path)
                except Exception:
                    logger.exception("Failed to load %s", yaml_path)

    def _load_from_env(self):
        """Load config from environment variables.

        Convention: TRADESTREAM_{NAMESPACE}_{KEY} e.g. TRADESTREAM_RISK_MAX_POSITION_PCT
        """
        prefix = "TRADESTREAM_"
        for key, value in os.environ.items():
            if not key.startswith(prefix):
                continue
            parts = key[len(prefix) :].lower().split("_", 1)
            if len(parts) != 2:
                continue
            ns, config_key = parts
            if ns not in VALID_NAMESPACES:
                continue
            self._config.setdefault(ns, {})[config_key] = _coerce_value(value)

    def _load_from_db(self):
        """Load config overrides from database (sync placeholder)."""
        if not self._db_pool:
            return
        # Database loading is handled asynchronously via load_from_db_async
        pass

    async def load_from_db_async(self):
        """Load config overrides from database."""
        if not self._db_pool:
            return
        try:
            async with self._db_pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT namespace, key, value FROM config_overrides "
                    "WHERE active = true ORDER BY namespace, key"
                )
            with self._lock:
                for row in rows:
                    ns = row["namespace"]
                    if ns in VALID_NAMESPACES:
                        self._config.setdefault(ns, {})[row["key"]] = _coerce_value(
                            row["value"]
                        )
            logger.info("Loaded %d config overrides from database", len(rows))
        except Exception:
            logger.exception("Failed to load config from database")

    def get_all(self, mask_secrets: bool = True) -> Dict[str, Dict[str, Any]]:
        """Get all config, optionally masking secrets."""
        with self._lock:
            result = copy.deepcopy(self._config)
        if mask_secrets:
            _mask_secrets(result)
        return result

    def get_namespace(
        self, namespace: str, mask_secrets: bool = True
    ) -> Optional[Dict[str, Any]]:
        """Get config for a specific namespace."""
        if namespace not in VALID_NAMESPACES:
            return None
        with self._lock:
            data = copy.deepcopy(self._config.get(namespace, {}))
        if mask_secrets:
            _mask_secrets_flat(data)
        return data

    def update_namespace(
        self, namespace: str, updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update config for a namespace at runtime. Returns updated config."""
        if namespace not in VALID_NAMESPACES:
            raise ValueError(f"Invalid namespace: {namespace}")

        errors = validate_namespace(namespace, updates, partial=True)
        if errors:
            raise ConfigValidationError(errors)

        with self._lock:
            self._config.setdefault(namespace, {}).update(updates)
            result = copy.deepcopy(self._config[namespace])

        self._notify_watchers(namespace)
        return result

    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate a config blob. Returns {"valid": bool, "errors": [...]}."""
        all_errors = []
        for ns, values in config.items():
            if ns not in VALID_NAMESPACES:
                all_errors.append({"field": ns, "message": f"Unknown namespace: {ns}"})
                continue
            if not isinstance(values, dict):
                all_errors.append(
                    {"field": ns, "message": "Namespace value must be a mapping"}
                )
                continue
            all_errors.extend(validate_namespace(ns, values))

        return {"valid": len(all_errors) == 0, "errors": all_errors}

    def get_schema(self) -> Dict[str, Any]:
        """Return the config schema."""
        return copy.deepcopy(CONFIG_SCHEMA)

    def on_change(self, callback: Callable):
        """Register a callback for config changes."""
        self._watchers.append(callback)

    def _notify_watchers(self, namespace: str):
        for cb in self._watchers:
            try:
                cb(namespace)
            except Exception:
                logger.exception("Config watcher callback failed")

    # --- Hot-reload ---

    def start_watching(self, interval: float = 2.0):
        """Start watching config directory for changes."""
        if not self._config_dir or self._watching:
            return
        self._watching = True
        self._watch_thread = threading.Thread(
            target=self._watch_loop,
            args=(interval,),
            daemon=True,
        )
        self._watch_thread.start()
        logger.info("Started config file watcher on %s", self._config_dir)

    def stop_watching(self):
        """Stop watching config directory."""
        self._watching = False
        if self._watch_thread:
            self._watch_thread.join(timeout=5)
            self._watch_thread = None

    def _watch_loop(self, interval: float):
        """Poll config files for modifications."""
        import time

        mtimes: Dict[str, float] = {}
        while self._watching:
            if self._config_dir and self._config_dir.exists():
                changed = False
                for ns in VALID_NAMESPACES:
                    yaml_path = self._config_dir / f"{ns}.yaml"
                    if yaml_path.exists():
                        mtime = yaml_path.stat().st_mtime
                        if mtimes.get(str(yaml_path)) != mtime:
                            mtimes[str(yaml_path)] = mtime
                            changed = True
                if changed:
                    logger.info("Config file change detected, reloading")
                    self.load()
                    for ns in VALID_NAMESPACES:
                        self._notify_watchers(ns)
            time.sleep(interval)


def validate_namespace(
    namespace: str, values: Dict[str, Any], partial: bool = False
) -> List[Dict[str, str]]:
    """Validate values against the namespace schema."""
    errors = []
    schema = NAMESPACE_SCHEMAS.get(namespace, {})
    if not schema:
        return errors

    for key, value in values.items():
        if key not in schema:
            # Allow unknown keys (forward compatibility)
            continue
        field_schema = schema[key]
        expected_type = field_schema.get("type")
        if expected_type and not _type_check(value, expected_type):
            errors.append(
                {
                    "field": f"{namespace}.{key}",
                    "message": f"Expected type {expected_type}, got {type(value).__name__}",
                }
            )
            continue
        if "min" in field_schema and isinstance(value, (int, float)):
            if value < field_schema["min"]:
                errors.append(
                    {
                        "field": f"{namespace}.{key}",
                        "message": f"Value {value} below minimum {field_schema['min']}",
                    }
                )
        if "max" in field_schema and isinstance(value, (int, float)):
            if value > field_schema["max"]:
                errors.append(
                    {
                        "field": f"{namespace}.{key}",
                        "message": f"Value {value} above maximum {field_schema['max']}",
                    }
                )
        if "choices" in field_schema and value not in field_schema["choices"]:
            errors.append(
                {
                    "field": f"{namespace}.{key}",
                    "message": f"Invalid value '{value}', must be one of {field_schema['choices']}",
                }
            )

    return errors


def _type_check(value: Any, expected: str) -> bool:
    """Check if value matches expected type string."""
    type_map = {
        "str": str,
        "int": int,
        "float": (int, float),
        "bool": bool,
        "list": list,
    }
    expected_type = type_map.get(expected)
    if expected_type is None:
        return True
    return isinstance(value, expected_type)


def _coerce_value(value: str) -> Any:
    """Coerce string value to appropriate Python type."""
    if value.lower() in ("true", "yes"):
        return True
    if value.lower() in ("false", "no"):
        return False
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value


def _mask_secrets(config: Dict[str, Any]):
    """Mask secret values in nested config dict."""
    for ns, values in config.items():
        if isinstance(values, dict):
            _mask_secrets_flat(values)


def _mask_secrets_flat(data: Dict[str, Any]):
    """Mask secret values in a flat dict."""
    for key in data:
        if SECRET_PATTERNS.search(key):
            data[key] = MASK
