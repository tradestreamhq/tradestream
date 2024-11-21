package com.verlumen.tradestream.ingestion;

/**
 * ThinMarketTimer ensures that candles are produced even during periods of little to no trading volume.
 * This timer can be started and stopped based on specific conditions in the market, ensuring that
 * candle generation aligns with expected intervals regardless of market activity.
 */
interface ThinMarketTimer {
  
  /**
   * Starts the timer for tracking intervals during thin market conditions.
   * This ensures that candles are generated even if no trades occur within the expected timeframe.
   */
  void start();

  /**
   * Stops the timer for tracking intervals during thin market conditions.
   * This can be used when normal trading activity resumes, and candles are naturally produced by incoming trades.
   */
  void stop();
}
