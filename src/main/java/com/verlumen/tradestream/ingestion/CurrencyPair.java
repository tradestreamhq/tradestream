package com.verlumen.tradestream.ingestion;

import com.google.auto.value.AutoValue;

@AutoValue
abstract static class CurrencyPair {
  private static Currency create(Currency base, Currency counter) {
    return new AutoValue_CurrencyPairMetadata_CurrencyPair(base, counter);
  }

  abstract Currency base();

  abstract Currency counter();
}
