package com.verlumen.tradestream.instruments;

import static com.google.common.base.Preconditions.checkArgument;
import static com.google.common.collect.MoreCollectors.onlyElement;
import static com.google.common.collect.ImmutableList.toImmutableList;

-import com.google.common.base.Splitter;
import com.google.common.collect.ImmutableList;
import java.util.NoSuchElementException;
import java.util.stream.Stream;

/**
 * Represents a currency pair, which is a combination of two currencies.
 *
 * <p>A currency pair expresses the exchange rate between two currencies, with the first currency
 * (the "base") being traded and the second currency (the "counter") being the one against which the
 * base currency is traded.
 *
 * </p>
 *
 * <p>For example, a currency pair might look like "EUR/USD" or "BTC-ETH", indicating how many units
 * of the counter currency (e.g., USD) are required to purchase one unit of the base currency (e.g.,
 * EUR).
 * </p>
 */
public record class CurrencyPair {
  // Constants for possible delimiters in the currency pair symbol.
  private static final String FORWARD_SLASH = "/";
  private static final String HYPHEN = "-";

  /**
   * Creates a {@link CurrencyPair} from a given symbol.
   *
   * <p>The symbol should use either "/" or "-" as a delimiter, for example:
   *
   * <ul>
   *   <li>"EUR/USD"</li>
   *   <li>"BTC-ETH"</li>
   * </ul>
   *
   * <p>This method will:
   *
   * <ol>
   *   <li>Determine which delimiter is used in the symbol.</li>
   *   <li>Split the symbol into base and counter currency codes.</li>
   *   <li>Convert these codes to uppercase and ensure they're distinct.</li>
   * </ol>
   *
   * @param symbol a string representing the currency pair (e.g., "EUR/USD" or "BTC-ETH").
   * @return a {@link CurrencyPair} object representing the base and counter currencies.
   * @throws IllegalArgumentException if the symbol is invalid, ambiguous, or does not contain
   *     exactly two currencies.
   */
  public static CurrencyPair fromSymbol(String symbol) {
    ImmutableList<String> symbolParts = splitSymbol(symbol);
    Currency base = Currency.create(symbolParts.get(0));
    Currency counter = Currency.create(symbolParts.get(1));
    return new CurrencyPair(base, counter);
  }

  /**
   * Splits the given currency pair symbol into its base and counter currency components.
   *
   * <p>This method attempts to split the symbol using either "/" or "-" as a delimiter. It also
   * ensures that exactly two parts are extracted, both are non-empty, and they are converted to
   * uppercase and distinct values.
   *
   * @param symbol The currency pair symbol string (e.g., "EUR/USD" or "BTC-ETH").
   * @return An {@link ImmutableList} containing the base and counter currencies.
   * @throws IllegalArgumentException If the symbol is null or does not match the expected format
   *     (e.g., doesn't contain a delimiter, contains more than two parts)
   */
  private static ImmutableList<String> splitSymbol(String symbol) {
    try {
      // Determine the delimiter used in the symbol.
      String delimiter =
          Stream.of(FORWARD_SLASH, HYPHEN).filter(symbol::contains).collect(onlyElement());

      // Split the symbol using the determined delimiter.
      Splitter splitter = Splitter.on(delimiter).trimResults().omitEmptyStrings();

      // Extract and normalize the parts.
      ImmutableList<String> parts =
          splitter.splitToStream(symbol).map(String::toUpperCase).distinct().collect(toImmutableList());

      // Validate that exactly two parts are present.
      checkArgument(parts.size() == 2, "Symbol must contain exactly two currencies: %s", symbol);

      return parts;
    } catch (NoSuchElementException | IllegalArgumentException e) {
      throw new IllegalArgumentException(
          String.format("Unable to parse currency pair, invalid symbol: \"%s\".", symbol), e);
    }
  }

  public String symbol() {
    return base().symbol() + FORWARD_SLASH + counter().symbol();
  }
}
