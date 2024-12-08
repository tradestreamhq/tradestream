package com.verlumen.tradestream.instruments;

import com.google.auto.value.AutoValue;
import com.google.common.base.Splitter;

@AutoValue
abstract static class CurrencyPair {
  public static CurrencyPair fromSymbol(String symbol) {
    String delimitter = Stream.of(FORWARD_SLASH, HYPHEN)
      .filter(symbol::contains)
      .collect(onlyElement());
    Splitter splitter = Splitter.on(delimiter)
      .trimResults()
      .omitEmptyStrings();
    Currency base = Currency.create(splitter.split(symbol)[0].toUpperCase());
    Currency counter = Currency.create(splitter.split(symbol)[1].toUpperCase());
    return create(base, counter);
  }

  private static CurrencyPair create(Currency base, Currency counter) {
    return new AutoValue_CurrencyPair(base, counter);
  }

  abstract Currency base();

  abstract Currency counter();
}
