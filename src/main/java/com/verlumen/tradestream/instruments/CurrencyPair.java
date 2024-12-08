package com.verlumen.tradestream.instruments;

import static com.google.common.collect.ImmutableList.toImmutableList;
import static com.google.common.collect.MoreCollectors.onlyElement;

import com.google.auto.value.AutoValue;
import com.google.common.base.Splitter;
import com.google.common.collect.ImmutableList;

@AutoValue
public abstract class CurrencyPair {
  public static CurrencyPair fromSymbol(String symbol) {
    String delimitter = Stream.of(FORWARD_SLASH, HYPHEN)
      .filter(symbol::contains)
      .collect(onlyElement());
    Splitter splitter = Splitter.on(delimiter)
      .trimResults()
      .omitEmptyStrings();
    ImmutableList<String> symbolParts = splitter.split(symbol)
      .stream()
      .map(String::toUpperCase)
      .distinct()
      .collect(toImmutableList());
    Currency base = Currency.create(symbolParts.get(0));
    Currency counter = Currency.create(symbolParts.get(1));
    return create(base, counter);
  }

  private static CurrencyPair create(Currency base, Currency counter) {
    return new AutoValue_CurrencyPair(base, counter);
  }

  abstract Currency base();

  abstract Currency counter();
}
