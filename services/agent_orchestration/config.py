"""Configuration for the Agent Orchestration Layer."""

# Cycle scheduling
DEFAULT_CYCLE_INTERVAL_SECONDS = 3600  # 1 hour between discovery cycles
MIN_CYCLE_INTERVAL_SECONDS = 300  # 5 minutes minimum

# Discovery phase
CANDIDATES_PER_CYCLE = 5  # Number of strategy candidates to generate per cycle
MAX_LLM_ITERATIONS = 20  # Max LLM tool-call iterations for discovery

# Validation phase
MIN_SHARPE_RATIO = 0.5  # Minimum Sharpe ratio to pass validation
MIN_WIN_RATE = 0.45  # Minimum win rate
MAX_DRAWDOWN = -0.30  # Maximum allowed drawdown (negative)
BACKTEST_SYMBOLS = ["BTC-USD", "ETH-USD"]  # Symbols to backtest against
WALK_FORWARD_WINDOWS = 5  # Number of walk-forward windows

# Promotion phase
INITIAL_ALLOCATION_WEIGHT = 0.05  # 5% initial allocation for promoted strategies
MAX_PROMOTED_PER_CYCLE = 2  # Max strategies to promote in one cycle

# Monitoring phase
PERFORMANCE_LOOKBACK_DAYS = 30
ALLOCATION_INCREASE_THRESHOLD = 0.7  # Sharpe above this => increase allocation
ALLOCATION_DECREASE_THRESHOLD = 0.3  # Sharpe below this => decrease allocation
RETIREMENT_SHARPE_THRESHOLD = 0.0  # Retire if Sharpe drops below this
RETIREMENT_LOOKBACK_DAYS = 14
MAX_ALLOCATION_WEIGHT = 0.25  # Cap at 25% allocation

# State persistence
STATE_FILE_DEFAULT = "/tmp/agent_orchestration_state.json"

# Circuit breaker
CIRCUIT_BREAKER_FAILURE_THRESHOLD = 3
CIRCUIT_BREAKER_RECOVERY_SECONDS = 300

# Retry settings
RETRY_MAX_ATTEMPTS = 3
RETRY_BASE_DELAY_SECONDS = 1.0
RETRY_MAX_DELAY_SECONDS = 30.0
RETRY_BACKOFF_MULTIPLIER = 2.0

TRANSIENT_EXCEPTIONS = (
    ConnectionError,
    TimeoutError,
    OSError,
)

# Phase names for logging
PHASE_DISCOVERY = "discovery"
PHASE_VALIDATION = "validation"
PHASE_PROMOTION = "promotion"
PHASE_MONITORING = "monitoring"
