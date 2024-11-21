package com.verlumen.tradestream.ingestion;

import static com.google.common.collect.ImmutableList.toImmutableList;

import com.google.common.collect.ImmutableList;
import org.knowm.xchange.currency.CurrencyPair;
import java.util.function.Supplier;

interface CurrencyPairSupplier extends Supplier<ImmutableList<CurrencyPairMetadata>> {
  default ImmutableList<CurrencyPair> currencyPairs() {
    return get()
      .stream()
      .map(CurrencyPairMetadata::currencyPair)
      .collect(toImmutableList());
  }
}
