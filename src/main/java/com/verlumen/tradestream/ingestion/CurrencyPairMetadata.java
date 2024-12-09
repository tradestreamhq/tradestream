package com.verlumen.tradestream.ingestion;

import com.google.auto.value.AutoValue;
import com.verlumen.tradestream.instruments.Currency;
import com.verlumen.tradestream.instruments.CurrencyPair;

import java.math.BigDecimal;

/**
 * Represents metadata for a currency pair, including its {@link CurrencyPair} and associated market capitalization.
 */
@AutoValue
abstract class CurrencyPairMetadata {
  /**
   * Factory method to create a {@link CurrencyPairMetadata} instance.
   *
   * @param symbol          the symbol representing the currency pair, e.g., "BTC/USD" or "ETH-BTC".
   * @param marketCapValue  the market capitalization value for the pair, in terms of the counter currency.
   * @return a new {@link CurrencyPairMetadata} instance.
   */
  static CurrencyPairMetadata create(String symbol, BigDecimal marketCapValue) {
    // Parse the currency pair from the symbol.
    CurrencyPair currencyPair = CurrencyPair.fromSymbol(symbol);

    // Create a MarketCap object using the market capitalization value and the counter currency.
    MarketCap marketCap = MarketCap.create(marketCapValue, currencyPair.counter());

    // Create and return the CurrencyPairMetadata object.
    return create(currencyPair, marketCap);
  }

  /**
   * Private factory method to create a {@link CurrencyPairMetadata} instance.
   *
   * @param currencyPair the currency pair for which metadata is being created.
   * @param marketCap    the market capitalization associated with the currency pair.
   * @return a new {@link CurrencyPairMetadata} instance.
   */
  private static CurrencyPairMetadata create(CurrencyPair currencyPair, MarketCap marketCap) {
    return new AutoValue_CurrencyPairMetadata(currencyPair, marketCap);
  }

  /**
   * Returns the {@link CurrencyPair} associated with this metadata.
   *
   * @return the currency pair.
   */
  abstract CurrencyPair currencyPair();

  /**
   * Returns the {@link MarketCap} associated with this currency pair.
   *
   * @return the market capitalization details.
   */
  abstract MarketCap marketCap();

  /**
   * Represents market capitalization details, including its value and associated currency.
   */
  @AutoValue
  abstract static class MarketCap {
    /**
     * Factory method to create a {@link MarketCap} instance.
     *
     * @param value    the market capitalization value.
     * @param currency the currency in which the market cap is denominated (typically the counter currency).
     * @return a new {@link MarketCap} instance.
     */
    private static MarketCap create(BigDecimal value, Currency currency) {
      if (value == null || value.compareTo(BigDecimal.ZERO) < 0) {
        throw new IllegalArgumentException("Market cap value must not be null or negative.");
      }
      if (currency == null) {
        throw new IllegalArgumentException("Currency must not be null.");
      }
      return new AutoValue_CurrencyPairMetadata_MarketCap(value, currency);
    }

    /**
     * Returns the market capitalization value.
     *
     * @return the market cap value.
     */
    abstract BigDecimal value();

    /**
     * Returns the currency in which the market cap is denominated.
     *
     * @return the currency.
     */
    abstract Currency currency();
  }
}
