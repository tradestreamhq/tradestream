package com.verlumen.tradestream.instruments;

import java.io.Serializable;

/**
 * Represents a currency with a unique symbol.
 *
 * A {@link Currency} object encapsulates the symbol of a currency, which can be used in contexts
 * such as trading, forex, or financial applications.
 */
public record Currency(String symbol) implements Serializable {
  /**
   * Factory method to create a {@link Currency} instance.
   *
   * @param symbol the symbol of the currency, typically in uppercase and following ISO 4217 standards
   *             (e.g., "USD" for US Dollar, "EUR" for Euro, "BTC" for Bitcoin).
   * @return a new {@link Currency} instance with the given symbol.
   * @throws IllegalArgumentException if the symbol is null or empty.
   */
  static Currency create(String symbol) {
    if (symbol == null || symbol.isEmpty()) {
      throw new IllegalArgumentException("Currency symbol must not be null or empty.");
    }
    return new Currency(symbol);
  }
}
