package com.verlumen.tradestream.backtesting;

import com.verlumen.tradestream.marketdata.Candle;
import java.io.IOException;
import java.util.List;

/** Interface for loading historical OHLCV candle data for backtesting. */
public interface HistoricalDataLoader {
  /**
   * Loads historical candle data from a source.
   *
   * @return a list of candles sorted chronologically
   * @throws IOException if the data source cannot be read
   */
  List<Candle> loadCandles() throws IOException;
}
