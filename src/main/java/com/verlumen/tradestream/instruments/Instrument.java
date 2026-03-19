package com.verlumen.tradestream.instruments;

import com.verlumen.tradestream.marketdata.AssetClass;

/**
 * A tradable instrument with an associated asset class.
 *
 * <p>Generalizes the concept of a trading instrument beyond crypto currency pairs to support
 * stocks, forex, and commodities. For crypto and forex, the symbol is a pair (e.g., "BTC/USD",
 * "EUR/USD"). For stocks and commodities, the symbol is a ticker (e.g., "AAPL", "WTI").
 */
public record Instrument(String symbol, AssetClass assetClass) {

  /**
   * Creates an Instrument from a symbol string and asset class.
   *
   * @param symbol Normalized symbol (e.g., "BTC/USD", "AAPL", "EUR/USD", "WTI")
   * @param assetClass The asset class this instrument belongs to
   */
  public static Instrument create(String symbol, AssetClass assetClass) {
    return new Instrument(symbol, assetClass);
  }

  /** Creates a crypto instrument from an existing CurrencyPair. */
  public static Instrument fromCurrencyPair(CurrencyPair pair) {
    return new Instrument(pair.symbol(), AssetClass.CRYPTO);
  }

  /** Creates a stock instrument from a ticker symbol. */
  public static Instrument stock(String ticker) {
    return new Instrument(ticker.toUpperCase(), AssetClass.STOCKS);
  }

  /** Creates a forex instrument from a currency pair string. */
  public static Instrument forex(String pair) {
    return new Instrument(pair.toUpperCase(), AssetClass.FOREX);
  }

  /** Creates a commodity instrument from a symbol. */
  public static Instrument commodity(String symbol) {
    return new Instrument(symbol.toUpperCase(), AssetClass.COMMODITIES);
  }

  /**
   * Tries to convert this instrument to a CurrencyPair.
   *
   * @throws IllegalArgumentException if the symbol is not a valid pair format
   */
  public CurrencyPair toCurrencyPair() {
    return CurrencyPair.fromSymbol(symbol);
  }
}
