package com.verlumen.tradestream.ingestion;

import com.verlumen.tradestream.instruments.CurrencyPair;

import java.math.BigDecimal;

/**
 * Represents metadata for a currency pair, including its {@link CurrencyPair}
 * and associated market capitalization.
 */
record CurrencyPairMetadata(
  CurrencyPair currencyPair,
  BigDecimal marketCap
) {

  /**
   * Factory method to create a {@link CurrencyPairMetadata} instance from a symbol and market cap value.
   *
   * The symbol should be in the format "BASE/COUNTER" or "BASE-COUNTER".
   *
   * @param symbol         the symbol representing the currency pair, e.g., "BTC/USD" or "ETH-BTC".
   * @param marketCapValue the market capitalization value as a {@link BigDecimal}.
   * @return a new {@link CurrencyPairMetadata} instance.
   * @throws IllegalArgumentException if the marketCapValue is null or negative.
   */
  static CurrencyPairMetadata create(String symbol, BigDecimal marketCapValue) {
    if (marketCapValue == null || marketCapValue.compareTo(BigDecimal.ZERO) < 0) {
      throw new IllegalArgumentException("Market cap value must be non-null and non-negative.");
    }
    return create(CurrencyPair.fromSymbol(symbol), marketCapValue);
  }

  /**
   * Private factory method to create a {@link CurrencyPairMetadata} instance.
   *
   * @param currencyPair the {@link CurrencyPair} associated with the metadata.
   * @param marketCap    the market capitalization value as a {@link BigDecimal}.
   * @return a new {@link CurrencyPairMetadata} instance.
   */
  private static CurrencyPairMetadata create(CurrencyPair currencyPair, BigDecimal marketCap) {
    return new CurrencyPairMetadata(currencyPair, marketCap);
  }
}
