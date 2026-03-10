"""Configuration for the Orchestrator Agent."""

# Scheduling intervals (seconds)
SIGNAL_GENERATOR_INTERVAL_SECONDS = 60
STRATEGY_PROPOSER_INTERVAL_SECONDS = 1800  # 30 minutes

# Circuit breaker settings
CIRCUIT_BREAKER_FAILURE_THRESHOLD = 3
CIRCUIT_BREAKER_RECOVERY_SECONDS = 300  # 5 minutes

# Retry settings
RETRY_MAX_ATTEMPTS = 3
RETRY_BASE_DELAY_SECONDS = 1.0
RETRY_MAX_DELAY_SECONDS = 30.0
RETRY_BACKOFF_MULTIPLIER = 2.0

# Transient error patterns (connection/timeout issues)
TRANSIENT_EXCEPTIONS = (
    ConnectionError,
    TimeoutError,
    OSError,
)

# Agent names
AGENT_SIGNAL_GENERATOR = "signal_generator"
AGENT_OPPORTUNITY_SCORER = "opportunity_scorer"
AGENT_STRATEGY_PROPOSER = "strategy_proposer"
