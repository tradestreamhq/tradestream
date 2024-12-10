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
 * <p>
 * A currency pair expresses the exchange rate between two currencies, with the first
 * currency (the "base") being traded and the second currency (the "counter") being
 * the one against which the base currency is traded.
 * </p>
 * For example, a currency pair might look like "EUR/USD" or "BTC-ETH", indicating
 * how many units of the counter currency (e.g., USD) are required to purchase one
 * unit of the base currency (e.g., EUR).
 */
@AutoValue
public abstract class CurrencyPair {
  // Constants for possible delimiters in the currency pair symbol.
  private static final String FORWARD_SLASH = "/";
  private static final String HYPHEN = "-";

  /**
   * Creates a {@link CurrencyPair} from a given symbol.
   * <p>
   * The symbol should use either "/" or "-" as a delimiter, for example:
   * <ul>
   *   <li>"EUR/USD"</li>
   *   <li>"BTC-ETH"</li>
   * </ul>
   * This method will:
   * <ol>
   *   <li>Determine which delimiter is used in the symbol.</li>
   *   <li>Split the symbol into base and counter currency codes.</li>
   *   <li>Convert these codes to uppercase and ensure they're distinct.</li>
   * </ol>
   *
   * @param symbol a string representing the currency pair (e.g., "EUR/USD" or "BTC-ETH").
   * @return a {@link CurrencyPair} object representing the base and counter currencies.
   * @throws IllegalArgumentException if the symbol is invalid, ambiguous, or does not
   *                                  contain exactly two currencies.
   */
  public static CurrencyPair fromSymbol(String symbol) {
    SymbolParts symbolParts = SymbolParts.fromSymbol(symbol);
    Currency base = Currency.create(symbolParts.parts().get(0));
    Currency counter = Currency.create(symbolParts.parts().get(1));
    return create(base, counter, symbolParts.delimiter());
  }

  /**
   * Creates a {@link CurrencyPair} instance from the given base and counter currencies and the
   * delimiter used in the original symbol.
   *
   * @param base      the base currency (e.g., EUR in EUR/USD)
   * @param counter   the counter currency (e.g., USD in EUR/USD)
   * @param delimiter the delimiter used in the original symbol ("/" or "-")
   * @return a new {@link CurrencyPair} instance
   */
  private static CurrencyPair create(Currency base, Currency counter, String delimiter) {
    return new AutoValue_CurrencyPair(base, counter, delimiter);
  }

  /**
   * Returns the base currency of this currency pair.
   * <p>
   * The base currency is the first currency listed in the pair and is the one being traded.
   *
   * @return the base {@link Currency}
   */
  public abstract Currency base();

  /**
   * Returns the counter currency of this currency pair.
   * <p>
   * The counter currency is the second currency listed in the pair and is the one
   * used to quote the value of the base currency.
   *
   * @return the counter {@link Currency}
   */
  public abstract Currency counter();

  /**
   * Returns the delimiter used in this currency pair's original symbol.
   * <p>
   * Typically, the delimiter is "/" or "-".
   *
   * @return the delimiter used in the original symbol
   */
  abstract String delimiter();

  /**
   * Returns the currency pair symbol using the original delimiter.
   * <p>
   * For example, if the base is EUR and the counter is USD, and the delimiter was "/",
   * this method returns "EUR/USD".
   *
   * @return a string representation of the currency pair symbol using the original delimiter
   */
  public String symbol() {
    return symbolWithCustomDelimiter(delimiter());
  }

  public CurrencyPair withCustomDelimiter(String delimiter) {
    return fromSymbol(symbolWithCustomDelimiter(delimiter));
  }

  /**
   * Returns the currency pair symbol using a custom delimiter.
   * <p>
   * For example, if you pass "-" as the delimiter, and the pair is EUR and USD, this method
   * returns "EUR-USD".
   *
   * @param delimiter the custom delimiter to use when constructing the symbol
   * @return a string representation of the currency pair symbol using the specified delimiter
   */
  private String symbolWithCustomDelimiter(String delimiter) {
    return String.format("%s%s%s", base().symbol(), delimiter, counter().symbol());
  }

  /**
   * Represents the parsed components of a currency pair symbol, including the delimiter
   * and the separate currency parts.
   */
  @AutoValue
  static abstract class SymbolParts {
    /**
     * Parses a currency pair symbol and extracts its delimiter and parts.
     * <p>
     * This method:
     * <ol>
     *   <li>Identifies which delimiter ("/" or "-") is used in the symbol.</li>
     *   <li>Splits the symbol into two parts: base and counter currencies.</li>
     *   <li>Normalizes these parts to uppercase and ensures distinctness.</li>
     * </ol>
     *
     * @param symbol the currency pair symbol to parse
     * @return a {@link SymbolParts} object containing the delimiter and the parts
     * @throws IllegalArgumentException if the symbol does not contain exactly two distinct parts
     *                                  or if the delimiter is ambiguous
     */
    static SymbolParts fromSymbol(String symbol) {
      try {
        // Determine the delimiter used in the symbol.
        String delimiter = Stream.of(FORWARD_SLASH, HYPHEN)
            .filter(symbol::contains)
            .collect(onlyElement());

        // Split the symbol using the determined delimiter.
        Splitter splitter = Splitter.on(delimiter)
            .trimResults()
            .omitEmptyStrings();

        // Extract and normalize the parts.
        ImmutableList<String> parts = splitter.splitToStream(symbol)
            .map(String::toUpperCase)
            .distinct()
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
     * Creates a {@link SymbolParts} object.
     *
     * @param delimiter the delimiter used in the original symbol
     * @param parts     the two currency codes parsed from the symbol
     * @return a {@link SymbolParts} instance
     */
    private static SymbolParts create(String delimiter, ImmutableList<String> parts) {
      return new AutoValue_CurrencyPair_SymbolParts(delimiter, parts);
    }

    /**
     * Returns the delimiter used in the currency pair symbol.
     *
     * @return the delimiter ("/" or "-")
     */
    abstract String delimiter();

    /**
     * Returns the parts of the currency pair symbol, i.e., the base and counter currency codes.
     *
     * @return an {@link ImmutableList} of two strings, representing the base and counter currencies
     */
    abstract ImmutableList<String> parts();
  }
}
