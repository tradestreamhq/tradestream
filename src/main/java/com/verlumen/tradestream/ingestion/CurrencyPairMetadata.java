package com.verlumen.tradestream.ingestion;

import com.google.auto.value.AutoValue;
import com.verlumen.tradestream.instruments.Currency;
import com.verlumen.tradestream.instruments.CurrencyPair;

import java.math.BigDecimal;

/**
 * Represents metadata for a currency pair, including its {@link CurrencyPair} 
 * and associated market capitalization.
 */
@AutoValue
abstract class CurrencyPairMetadata {
  /**
   * Factory method to create a {@link CurrencyPairMetadata} instance from a symbol and market cap value.
   *
   * The symbol should be in the format "BASE/COUNTER" or "BASE-COUNTER".
   *
   * @param symbol    the symbol representing the currency pair, e.g., "BTC/USD" or "ETH-BTC".
   * @param marketCap the market capitalization value for the pair, in terms of the counter currency.
   * @return a new {@link CurrencyPairMetadata} instance.
   * @throws IllegalArgumentException if the symbol is invalid.
   */
  static CurrencyPairMetadata create(String symbol, BigDecimal marketCap) {
    // Parse the currency pair from the symbol.
    CurrencyPair currencyPair = CurrencyPair.fromSymbol(symbol);
    return create(currencyPair, marketCap);
  }

  /**
   * Factory method to create a {@link CurrencyPairMetadata} instance from a {@link CurrencyPair}
   * and a long market cap value.
   *
   * @param currencyPair the {@link CurrencyPair} instance.
   * @param marketCap the market capitalization value.
   * @return a new {@link CurrencyPairMetadata} instance.
   */
  static CurrencyPairMetadata create(String symbol, BigDecimal marketCapValue) {
    return create(CurrencyPair.fromSymbol(symbol), marketCapValue);
  }

  /**
   * Private factory method to create a {@link CurrencyPairMetadata} instance.
   *
   * @param currencyPair the {@link CurrencyPair} instance.
   * @param marketCap    the market capitalization value as a {@link BigDecimal}.
   * @return a new {@link CurrencyPairMetadata} instance.
   */
  private static CurrencyPairMetadata create(CurrencyPair currencyPair, BigDecimal marketCap) {
    if (marketCap == null || marketCap.compareTo(BigDecimal.ZERO) < 0) {
      throw new IllegalArgumentException("Market cap must be non-null and non-negative.");
    }
    return new AutoValue_CurrencyPairMetadata(currencyPair, marketCap);
  }

  /**
   * Returns the {@link CurrencyPair} associated with this metadata.
   *
   * @return the currency pair.
   */
  abstract CurrencyPair currencyPair();

  /**
   * Returns the market capitalization value for the currency pair.
   *
   * @return the market cap as a {@link BigDecimal}.
   */
  abstract BigDecimal marketCap();
}
