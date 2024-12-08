package com.verlumen.tradestream.instruments;

import com.google.auto.value.AutoValue;

import java.util.Currency;

@AutoValue
abstract static class CurrencyPair {
  private static Currency create(Currency base, Currency counter) {
    return new AutoValue_CurrencyPair(base, counter);
  }

  abstract Currency base();

  abstract Currency counter();
}
