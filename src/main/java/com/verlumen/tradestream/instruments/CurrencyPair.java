package com.verlumen.tradestream.instruments;

import static com.google.common.collect.ImmutableList.toImmutableList;
import static com.google.common.collect.MoreCollectors.onlyElement;

import com.google.auto.value.AutoValue;
import com.google.common.base.Splitter;
import com.google.common.collect.ImmutableList;

import java.util.stream.Stream;

/**
 * Represents a currency pair, which is a combination of two currencies.
 * A currency pair is used to express the exchange rate between the two currencies, 
 * with the first currency (base) being the one being traded, and the second currency (counter) being the one it is traded against.
 */
@AutoValue
public abstract class CurrencyPair {
  /**
   * Factory method to create a {@link CurrencyPair} from a string symbol.
   *
   * The symbol should be in the format "BASE/COUNTER" or "BASE-COUNTER", where "BASE" 
   * and "COUNTER" are the codes for the currencies in the pair. The method will:
   * - Determine the delimiter used ("/" or "-").
   * - Split the symbol into its base and counter currency components.
   * - Normalize the components to uppercase.
   * - Ensure the base and counter currencies are distinct.
   *
   * @param symbol the symbol representing the currency pair, e.g., "EUR/USD" or "BTC-ETH".
   * @return a {@link CurrencyPair} object representing the base and counter currencies.
   * @throws IllegalArgumentException if the symbol is invalid or if the delimiter is ambiguous.
   */
  public static CurrencyPair fromSymbol(String symbol) {
    // Determine the delimiter used in the symbol (either "/" or "-").
    // If both delimiters are present, or none is found, it will throw an exception.
    String delimiter = Stream.of(FORWARD_SLASH, HYPHEN)
      .filter(symbol::contains) // Retain only delimiters that are present in the symbol.
      .collect(onlyElement()); // Ensure exactly one delimiter is found.

    // Split the symbol using the determined delimiter.
    Splitter splitter = Splitter.on(delimiter)
      .trimResults() // Remove any leading/trailing whitespace.
      .omitEmptyStrings(); // Ignore empty parts caused by consecutive delimiters.

    // Normalize the split parts (e.g., convert to uppercase and ensure uniqueness).
    ImmutableList<String> symbolParts = splitter.splitToStream(symbol)
      .map(String::toUpperCase) // Convert each part to uppercase for standardization.
      .distinct() // Ensure the base and counter currencies are distinct.
      .collect(toImmutableList());

    // Extract the base and counter currencies.
    Currency base = Currency.create(symbolParts.get(0));
    Currency counter = Currency.create(symbolParts.get(1));

    // Create and return a CurrencyPair object.
    return create(base, counter);
  }

  // Constants for possible delimiters in the currency pair symbol.
  private static final String FORWARD_SLASH = "/";
  private static final String HYPHEN = "-";

  /**
   * Private factory method to create a {@link CurrencyPair} object.
   *
   * @param base the base currency.
   * @param counter the counter currency.
   * @return a new {@link CurrencyPair} instance.
   */
  private static CurrencyPair create(Currency base, Currency counter) {
    return new AutoValue_CurrencyPair(base, counter);
  }

  /**
   * Returns the base currency of the pair.
   *
   * The base currency is the first currency in the pair and is the one being traded.
   *
   * @return the base currency.
   */
  public abstract Currency base();

  /**
   * Returns the counter currency of the pair.
   *
   * The counter currency is the second currency in the pair and is the one being traded against.
   *
   * @return the counter currency.
   */
  public abstract Currency counter();
}
