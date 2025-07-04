"""Configuration constants for Strategy Discovery Request Factory."""

# Fibonacci sequence windows in minutes for strategy discovery
# These represent different time horizons for backtesting
FIBONACCI_WINDOWS_MINUTES = [
    1597,  # ~1.1 days
    2584,  # ~1.8 days
    4181,  # ~2.9 days
    6765,  # ~4.7 days
    10946,  # ~7.6 days
    17711,  # ~12.3 days
    28657,  # ~19.9 days
    46368,  # ~32.2 days
    75025,  # ~52.1 days
    121393,  # ~84.3 days
]

# Default parameters for strategy discovery
DEFAULT_TOP_N = 5  # Number of top strategies to discover per window/type
DEFAULT_MAX_GENERATIONS = 30  # GA maximum generations
DEFAULT_POPULATION_SIZE = 50  # GA population size

# Service configuration defaults
DEFAULT_SERVICE_IDENTIFIER = "strategy_discovery_processor"

# Validation constants
MIN_FIBONACCI_WINDOW_MINUTES = 5  # Minimum meaningful window size
MAX_FIBONACCI_WINDOW_MINUTES = 525600  # 1 year in minutes


def validate_fibonacci_windows(windows: list) -> bool:
    """Validate Fibonacci windows configuration."""
    if not windows:
        return False

    for window in windows:
        if not isinstance(window, int):
            return False
        if (
            window < MIN_FIBONACCI_WINDOW_MINUTES
            or window > MAX_FIBONACCI_WINDOW_MINUTES
        ):
            return False

    # Check if sorted
    return windows == sorted(windows)


def validate_ga_parameters(max_generations: int, population_size: int) -> bool:
    """Validate genetic algorithm parameters."""
    return (
        isinstance(max_generations, int)
        and max_generations > 0
        and max_generations <= 1000
        and isinstance(population_size, int)
        and population_size > 0
        and population_size <= 10000
    )
