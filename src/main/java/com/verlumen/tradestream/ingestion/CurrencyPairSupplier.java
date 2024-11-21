package com.verlumen.tradestream.ingestion;

import static com.google.common.collect.ImmutableList.toImmutableList;

import com.google.common.collect.ImmutableList;
import java.util.function.Supplier;

interface CurrencyPairSupplier extends Supplier<ImmutableList<CurrencyPairMetadata>> {
  default ImmutableList<CurrencyPair> currencyPairs() {
    return currencyPairSupplier()
      .get()
      .stream()
      .map(CurrencyPairMetadata::currencyPair)
      .collect(toImmutableList());
  }
}
