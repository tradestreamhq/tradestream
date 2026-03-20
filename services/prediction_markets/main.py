"""Prediction Market Integration Service.

Fetches data from Polymarket (insider tracker) and Kalshi prediction markets,
generates trading signals from probability movements and insider activity,
and tracks correlation between prediction market signals and asset prices.
"""

import os
import signal
import sys
import time

from absl import app, flags, logging

from services.prediction_markets.kalshi_client import KalshiClient
from services.prediction_markets.polymarket_client import PolymarketInsiderClient
from services.prediction_markets.signal_generator import (
    PredictionMarketSignalGenerator,
    ThresholdConfig,
)
from services.prediction_markets.insider_detector import InsiderActivityDetector
from services.prediction_markets.correlation_tracker import CorrelationTracker

FLAGS = flags.FLAGS

flags.DEFINE_string(
    "run_mode",
    os.getenv("RUN_MODE", "wet"),
    "Run mode: 'wet' for live, 'dry' for dry run",
)
flags.DEFINE_string(
    "polymarket_api_url",
    os.getenv("POLYMARKET_INSIDER_API_URL", ""),
    "Base URL for polymarket-insider-tracker API.",
)
flags.DEFINE_string(
    "kalshi_base_url",
    os.getenv("KALSHI_BASE_URL", "https://api.elections.kalshi.com/trade-api/v2"),
    "Base URL for Kalshi API.",
)
flags.DEFINE_boolean(
    "polymarket_enabled",
    os.getenv("POLYMARKET_ENABLED", "true").lower() == "true",
    "Enable Polymarket integration.",
)
flags.DEFINE_boolean(
    "kalshi_enabled",
    os.getenv("KALSHI_ENABLED", "true").lower() == "true",
    "Enable Kalshi integration.",
)
flags.DEFINE_integer(
    "cache_ttl_seconds",
    int(os.getenv("CACHE_TTL_SECONDS", "60")),
    "Cache TTL in seconds for API responses.",
)
flags.DEFINE_integer(
    "poll_interval_seconds",
    int(os.getenv("POLL_INTERVAL_SECONDS", "60")),
    "Polling interval in seconds.",
)
flags.DEFINE_float(
    "api_request_timeout",
    float(os.getenv("API_REQUEST_TIMEOUT", "5.0")),
    "Timeout in seconds for API requests.",
)
flags.DEFINE_float(
    "bullish_threshold",
    float(os.getenv("BULLISH_THRESHOLD", "0.70")),
    "Probability threshold for bullish signals.",
)
flags.DEFINE_float(
    "bearish_threshold",
    float(os.getenv("BEARISH_THRESHOLD", "0.30")),
    "Probability threshold for bearish signals.",
)
flags.DEFINE_float(
    "spike_threshold",
    float(os.getenv("SPIKE_THRESHOLD", "0.10")),
    "Minimum probability change to trigger spike signal.",
)

_shutdown = False


def _handle_signal(signum, frame):
    global _shutdown
    logging.info(f"Received signal {signum}, shutting down...")
    _shutdown = True


def _build_polymarket_client():
    """Create Polymarket client if enabled and configured."""
    if not FLAGS.polymarket_enabled or not FLAGS.polymarket_api_url:
        logging.info("Polymarket integration disabled or not configured.")
        return None
    return PolymarketInsiderClient(
        base_url=FLAGS.polymarket_api_url,
        request_timeout=FLAGS.api_request_timeout,
        cache_ttl_seconds=FLAGS.cache_ttl_seconds,
    )


def _build_kalshi_client():
    """Create Kalshi client if enabled."""
    if not FLAGS.kalshi_enabled:
        logging.info("Kalshi integration disabled.")
        return None
    return KalshiClient(
        base_url=FLAGS.kalshi_base_url,
        request_timeout=FLAGS.api_request_timeout,
        cache_ttl_seconds=FLAGS.cache_ttl_seconds,
    )


def _run_check(
    polymarket_client, kalshi_client, signal_gen, insider_detector, correlation_tracker
):
    """Run one prediction market alpha check cycle."""
    events = []
    insider_alerts = []

    # Fetch Kalshi data
    if kalshi_client:
        try:
            result = kalshi_client.get_crypto_relevant_markets_safe()
            kalshi_markets = result.get("markets", [])
            freshness = "LIVE"
            if result.get("stale"):
                freshness = "CACHED"
            elif result.get("unavailable"):
                freshness = "UNAVAILABLE"
            logging.info(f"Kalshi: {freshness}, {len(kalshi_markets)} markets")

            # Convert Kalshi markets to events for signal generation
            for m in kalshi_markets:
                events.append(
                    {
                        "event_id": m.get("ticker", ""),
                        "source": "kalshi",
                        "question": m.get("title", m.get("subtitle", "")),
                        "category": _categorize_kalshi_market(m),
                        "probability": m.get("yes_price", 0),
                        "previous_probability": m.get("previous_yes_price", 0),
                        "volume": m.get("volume", 0),
                        "avg_volume": m.get("volume_24h", 0),
                    }
                )

            # Check for insider-like activity via anomaly detection
            anomalies = insider_detector.analyze_markets(kalshi_markets)
            for a in anomalies:
                logging.info(
                    f"Anomaly detected: {a.anomaly_type} on {a.market_id} "
                    f"({a.severity})"
                )
        except Exception as e:
            logging.error(f"Kalshi fetch failed: {e}")

    # Fetch Polymarket insider data
    if polymarket_client:
        try:
            alert_result = polymarket_client.get_recent_alerts_safe()
            insider_alerts = alert_result.get("data", [])
            freshness = "LIVE"
            if alert_result.get("stale"):
                freshness = "CACHED"
            elif alert_result.get("unavailable"):
                freshness = "UNAVAILABLE"
            logging.info(f"Polymarket: {freshness}, {len(insider_alerts)} alerts")
        except Exception as e:
            logging.error(f"Polymarket fetch failed: {e}")

    # Generate signals
    signals = signal_gen.generate_signals(events, insider_alerts)
    for s in signals:
        logging.info(
            f"Signal: {s.signal_type.value} | {s.affected_asset} | "
            f"strength={s.signal_strength:.2f} | {s.reasoning}"
        )

    return signals


def _categorize_kalshi_market(market: dict) -> str:
    """Categorize a Kalshi market by its series ticker."""
    ticker = market.get("ticker", "").upper()
    series = market.get("series_ticker", "").upper()

    if series.startswith("FED") or "RATE" in ticker:
        return "monetary_policy"
    if series.startswith("SEC") or series.startswith("CFTC"):
        return "regulatory"
    if "BTCETF" in ticker or "BTCETF" in series:
        return "btc_etf"
    if "ETHETF" in ticker or "ETHETF" in series:
        return "eth_etf"
    if any(k in ticker for k in ["ELECTION", "PRESIDENT", "SENATE"]):
        return "political"
    if any(k in ticker for k in ["CPI", "GDP", "JOBS", "INFLATION"]):
        return "economic"
    return "crypto_specific"


def main(argv):
    del argv  # Unused

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    logging.info("Starting Prediction Market Integration Service")
    logging.info(f"Run mode: {FLAGS.run_mode}")
    logging.info(f"Polymarket enabled: {FLAGS.polymarket_enabled}")
    logging.info(f"Kalshi enabled: {FLAGS.kalshi_enabled}")

    polymarket_client = _build_polymarket_client()
    kalshi_client = _build_kalshi_client()

    signal_gen = PredictionMarketSignalGenerator(
        config=ThresholdConfig(
            bullish_threshold=FLAGS.bullish_threshold,
            bearish_threshold=FLAGS.bearish_threshold,
            spike_threshold=FLAGS.spike_threshold,
        )
    )
    insider_detector = InsiderActivityDetector()
    correlation_tracker = CorrelationTracker()

    if FLAGS.run_mode == "dry":
        logging.info("Dry run: executing single check cycle.")
        _run_check(
            polymarket_client,
            kalshi_client,
            signal_gen,
            insider_detector,
            correlation_tracker,
        )
        logging.info("Dry run complete.")
    else:
        logging.info(f"Starting poll loop (interval={FLAGS.poll_interval_seconds}s)")
        while not _shutdown:
            try:
                _run_check(
                    polymarket_client,
                    kalshi_client,
                    signal_gen,
                    insider_detector,
                    correlation_tracker,
                )
            except Exception as e:
                logging.error(f"Check cycle failed: {e}")
            time.sleep(FLAGS.poll_interval_seconds)

    # Cleanup
    if polymarket_client:
        polymarket_client.close()
    if kalshi_client:
        kalshi_client.close()

    logging.info("Prediction Market Integration Service stopped.")


if __name__ == "__main__":
    app.run(main)
