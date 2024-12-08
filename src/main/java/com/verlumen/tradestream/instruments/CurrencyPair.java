package com.verlumen.tradestream.instruments;

import com.google.auto.value.AutoValue;

import java.util.Currency;

@AutoValue
abstract static class CurrencyPair {
  public static CurrencyPair fromSymbol(String symbol) {
    String delimitter = Stream.of(FORWARD_SLASH, HYPHEN)
      .filter(symbol::contains)
      .collect(onlyElement());
    Splitter splitter = Splitter.on(delimiter)
      .trimResults()
      .omitEmptyStrings();
    Currency base = Currency.create(symbol.split(delimiter)[0]);
    Currency counter = Currency.create(symbol.split(delimiter)[1]);
    return create(base, counter);
  }

  private static CurrencyPair create(Currency base, Currency counter) {
    return new AutoValue_CurrencyPair(base, counter);
  }

  abstract Currency base();

  abstract Currency counter();
}
