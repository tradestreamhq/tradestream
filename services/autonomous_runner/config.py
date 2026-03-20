"""Configuration for the autonomous signal generation runner."""

import os
from dataclasses import dataclass, field


@dataclass
class ParallelConfig:
    max_concurrent: int = 10
    min_concurrent: int = 3
    batch_delay_ms: int = 1000


@dataclass
class TimeoutConfig:
    symbol_timeout_seconds: float = 10.0
    symbol_timeout_max_seconds: float = 15.0
    total_timeout_seconds: float = 50.0


@dataclass
class LockConfig:
    ttl_seconds: int = 90
    stale_threshold_seconds: int = 120
    redis_key_prefix: str = "signal:lock:"


@dataclass
class CircuitBreakerServiceConfig:
    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    half_open_max_calls: int = 3


@dataclass
class CircuitBreakerConfigs:
    llm_service: CircuitBreakerServiceConfig = field(
        default_factory=CircuitBreakerServiceConfig
    )
    redis: CircuitBreakerServiceConfig = field(
        default_factory=lambda: CircuitBreakerServiceConfig(
            failure_threshold=3, recovery_timeout=30.0, half_open_max_calls=2
        )
    )


@dataclass
class AdaptiveConfig:
    latency_window_size: int = 10
    p95_threshold_ms: float = 8000.0
    p99_threshold_ms: float = 9000.0
    backpressure_max_overruns: int = 3
    cooldown_cycles: int = 2


@dataclass
class RiskConfig:
    max_concurrent_signals: int = 5
    max_signals_per_symbol_per_hour: int = 4
    min_confidence_threshold: float = 0.50
    max_portfolio_exposure_pct: float = 80.0
    max_single_position_pct: float = 20.0
    max_daily_loss_pct: float = 5.0
    max_drawdown_pct: float = 10.0


@dataclass
class KillSwitchConfig:
    redis_key: str = "autonomous:kill_switch"
    check_interval_seconds: int = 5


@dataclass
class Config:
    schedule: str = "*/1 * * * *"
    instance_id: str = ""
    symbols: list = field(
        default_factory=lambda: [
            "BTC-USD",
            "ETH-USD",
            "SOL-USD",
            "DOGE-USD",
            "AVAX-USD",
            "LINK-USD",
        ]
    )
    parallel: ParallelConfig = field(default_factory=ParallelConfig)
    timeouts: TimeoutConfig = field(default_factory=TimeoutConfig)
    locks: LockConfig = field(default_factory=LockConfig)
    circuit_breaker: CircuitBreakerConfigs = field(
        default_factory=CircuitBreakerConfigs
    )
    adaptive: AdaptiveConfig = field(default_factory=AdaptiveConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    kill_switch: KillSwitchConfig = field(default_factory=KillSwitchConfig)

    # MCP server URLs
    mcp_strategy_url: str = ""
    mcp_market_url: str = ""
    mcp_signal_url: str = ""
    mcp_learning_url: str = ""

    # API key
    openrouter_api_key: str = ""

    # Redis URL
    redis_url: str = ""

    @staticmethod
    def from_env() -> "Config":
        """Create config from environment variables."""
        cfg = Config(
            instance_id=os.environ.get("INSTANCE_ID", ""),
            openrouter_api_key=os.environ.get("OPENROUTER_API_KEY", ""),
            redis_url=os.environ.get("REDIS_URL", "redis://localhost:6379"),
            mcp_strategy_url=os.environ.get(
                "MCP_STRATEGY_URL", "http://localhost:8080"
            ),
            mcp_market_url=os.environ.get("MCP_MARKET_URL", "http://localhost:8081"),
            mcp_signal_url=os.environ.get("MCP_SIGNAL_URL", "http://localhost:8082"),
            mcp_learning_url=os.environ.get(
                "MCP_LEARNING_URL", "http://localhost:8083"
            ),
        )

        symbols_env = os.environ.get("SYMBOLS", "")
        if symbols_env:
            cfg.symbols = [s.strip() for s in symbols_env.split(",") if s.strip()]

        interval = os.environ.get("SIGNAL_FREQUENCY_MINUTES", "")
        if interval:
            cfg.schedule = f"*/{interval} * * * *"

        return cfg
