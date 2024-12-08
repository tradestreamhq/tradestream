package com.verlumen.tradestream.instruments;

import com.google.auto.value.AutoValue;

/**
 * Represents a currency with a unique name.
 *
 * A {@link Currency} object encapsulates the name of a currency, which can be used in contexts
 * such as trading, forex, or financial applications.
 */
@AutoValue
public abstract class Currency {
  /**
   * Factory method to create a {@link Currency} instance.
   *
   * @param symbol the symbol of the currency, typically in uppercase and following ISO 4217 standards
   *             (e.g., "USD" for US Dollar, "EUR" for Euro, "BTC" for Bitcoin).
   * @return a new {@link Currency} instance with the given name.
   * @throws IllegalArgumentException if the name is null or empty.
   */
  static Currency create(String symbol) {
    if (name == null || name.isEmpty()) {
      throw new IllegalArgumentException("Currency symbol must not be null or empty.");
    }
    return new AutoValue_Currency(symbol);
  }

  /**
   * Returns the name of the currency.
   *
   * The name is typically a three-character code (e.g., "USD", "EUR", "JPY"), but it can also
   * represent other forms of currency identifiers, such as cryptocurrency symbols (e.g., "BTC").
   *
   * @return the name of the currency.
   */
  public abstract String symbol();
}
