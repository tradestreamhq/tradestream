package com.verlumen.tradestream.marketdata;

import com.verlumen.tradestream.execution.RunMode;
import org.joda.time.Duration;

/**
 * Factory interface for creating CandleSource instances based on runtime configuration.
 */
public interface CandleSourceFactory {
  /**
   * Creates a CandleSource based on the provided configuration.
   *
   * @param runMode The execution mode (DRY or WET)
   * @param granularity The candle granularity
   * @param tiingoApiKey The Tiingo API key (required for WET mode)
   * @return A configured CandleSource instance
   */
  CandleSource create(RunMode runMode, Duration granularity, String tiingoApiKey);
} 