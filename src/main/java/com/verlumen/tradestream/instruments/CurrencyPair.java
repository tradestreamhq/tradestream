package com.verlumen.tradestream.instruments;

import static com.google.common.base.Preconditions.checkArgument;
import static com.google.common.collect.MoreCollectors.onlyElement;

import com.google.auto.value.AutoValue;
import com.google.common.base.Splitter;
import com.google.common.collect.ImmutableList;

import java.util.NoSuchElementException;
import java.util.stream.Stream;

/**
 * Represents a currency pair, which is a combination of two currencies.
 * A currency pair is used to express the exchange rate between two currencies, 
 * with the first currency (base) being traded, and the second currency (counter) being traded against.
 */
@AutoValue
public abstract class CurrencyPair {
  // Constants for possible delimiters in the currency pair symbol.
  private static final String FORWARD_SLASH = "/";
  private static final String HYPHEN = "-";

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
    // Extract the parts of the symbol using SymbolParts.
    SymbolParts symbolParts = SymbolParts.fromSymbol(symbol);

    // Extract the base and counter currencies.
    Currency base = Currency.create(symbolParts.parts().get(0));
    Currency counter = Currency.create(symbolParts.parts().get(1));

    // Create and return a CurrencyPair object.
    return create(base, counter, symbolParts.delimiter());
  }

  /**
   * Factory method to create a {@link CurrencyPair} instance.
   *
   * @param base the base currency.
   * @param counter the counter currency.
   * @param delimiter the delimiter used in the original symbol.
   * @return a {@link CurrencyPair} object.
   */
  private static CurrencyPair create(Currency base, Currency counter, String delimiter) {
    return new AutoValue_CurrencyPair(base, counter, delimiter);
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

  /**
   * Returns the delimiter used in the currency pair symbol.
   *
   * @return the delimiter (e.g., "/" or "-").
   */
  public abstract String delimiter();

  /**
   * Returns the formatted symbol representing the currency pair.
   *
   * @return the symbol (e.g., "BTC/USD" or "ETH-BTC").
   */
  public String symbol() {
    return String.format("%s%s%s", base().symbol(), delimiter(), counter().symbol());
  }

  /**
   * Represents the parsed components of a currency pair symbol.
   */
  @AutoValue
  static abstract class SymbolParts {
    /**
     * Factory method to parse a symbol and extract its parts.
     *
     * @param symbol the currency pair symbol to parse.
     * @return a {@link SymbolParts} object containing the delimiter and parts.
     * @throws IllegalArgumentException if the symbol is invalid or ambiguous.
     */
    static SymbolParts fromSymbol(String symbol) {
      try {
        // Determine the delimiter used in the symbol.
        String delimiter = Stream.of(FORWARD_SLASH, HYPHEN)
          .filter(symbol::contains) // Retain only delimiters that are present in the symbol.
          .collect(onlyElement()); // Ensure exactly one delimiter is found.

        // Split the symbol using the determined delimiter.
        Splitter splitter = Splitter.on(delimiter)
          .trimResults() // Remove any leading/trailing whitespace.
          .omitEmptyStrings(); // Ignore empty parts caused by consecutive delimiters.

        // Extract and normalize the parts.
        ImmutableList<String> parts = splitter.splitToStream(symbol)
          .map(String::toUpperCase) // Convert each part to uppercase for standardization.
          .distinct() // Ensure the base and counter currencies are distinct.
          .collect(ImmutableList.toImmutableList());

        // Validate that exactly two parts are present.
        checkArgument(parts.size() == 2, "Symbol must contain exactly two currencies: %s", symbol);

        return create(delimiter, parts);
      } catch (NoSuchElementException | IllegalArgumentException e) {
        throw new IllegalArgumentException(
          String.format("Unable to parse currency pair, invalid symbol: \"%s\".", symbol), e);
      }
    }

    /**
     * Factory method to create a {@link SymbolParts} object.
     *
     * @param delimiter the delimiter used in the symbol.
     * @param parts the list of currency codes (base and counter).
     * @return a {@link SymbolParts} object.
     */
    private static SymbolParts create(String delimiter, ImmutableList<String> parts) {
      return new AutoValue_CurrencyPair_SymbolParts(delimiter, parts);
    }

    /**
     * Returns the delimiter used in the symbol.
     *
     * @return the delimiter.
     */
    abstract String delimiter();

    /**
     * Returns the list of currency codes in the symbol.
     *
     * @return the list of parts (base and counter currencies).
     */
    abstract ImmutableList<String> parts();
  }
}
