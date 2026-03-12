package com.verlumen.tradestream.backtesting;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.util.Timestamps;
import com.verlumen.tradestream.marketdata.Candle;
import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;

/**
 * Loads historical OHLCV data from CSV files. Expected CSV format:
 * timestamp_millis,open,high,low,close,volume
 *
 * <p>The first line is treated as a header and skipped.
 */
public final class CsvHistoricalDataLoader implements HistoricalDataLoader {
  private final Path csvPath;
  private final String currencyPair;

  public CsvHistoricalDataLoader(Path csvPath, String currencyPair) {
    this.csvPath = csvPath;
    this.currencyPair = currencyPair;
  }

  @Override
  public List<Candle> loadCandles() throws IOException {
    try (BufferedReader reader =
        Files.newBufferedReader(csvPath, StandardCharsets.UTF_8)) {
      return parseCandles(reader);
    }
  }

  /**
   * Loads candles from a classpath resource.
   *
   * @param resourcePath path to the resource (e.g., "/testdata/btc_usd.csv")
   * @param currencyPair the currency pair label
   * @return list of candles
   * @throws IOException if the resource cannot be read
   */
  public static List<Candle> fromResource(String resourcePath, String currencyPair)
      throws IOException {
    try (InputStream is = CsvHistoricalDataLoader.class.getResourceAsStream(resourcePath)) {
      if (is == null) {
        throw new IOException("Resource not found: " + resourcePath);
      }
      try (BufferedReader reader =
          new BufferedReader(new InputStreamReader(is, StandardCharsets.UTF_8))) {
        return parseCandles(reader, currencyPair);
      }
    }
  }

  private List<Candle> parseCandles(BufferedReader reader) throws IOException {
    return parseCandles(reader, this.currencyPair);
  }

  private static List<Candle> parseCandles(BufferedReader reader, String currencyPair)
      throws IOException {
    ImmutableList.Builder<Candle> candles = ImmutableList.builder();
    String line = reader.readLine(); // skip header
    if (line == null) {
      return candles.build();
    }
    while ((line = reader.readLine()) != null) {
      line = line.trim();
      if (line.isEmpty()) {
        continue;
      }
      String[] parts = line.split(",");
      if (parts.length < 6) {
        continue;
      }
      long timestampMillis = Long.parseLong(parts[0].trim());
      double open = Double.parseDouble(parts[1].trim());
      double high = Double.parseDouble(parts[2].trim());
      double low = Double.parseDouble(parts[3].trim());
      double close = Double.parseDouble(parts[4].trim());
      double volume = Double.parseDouble(parts[5].trim());

      candles.add(
          Candle.newBuilder()
              .setTimestamp(Timestamps.fromMillis(timestampMillis))
              .setCurrencyPair(currencyPair)
              .setOpen(open)
              .setHigh(high)
              .setLow(low)
              .setClose(close)
              .setVolume(volume)
              .build());
    }
    return candles.build();
  }
}
