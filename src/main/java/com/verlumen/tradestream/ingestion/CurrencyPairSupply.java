package com.verlumen.tradestream.ingestion;

import static com.google.common.collect.ImmutableList.toImmutableList;

import com.google.auto.value.AutoValue;
import com.google.common.collect.ImmutableList;
import com.verlumen.tradestream.instruments.CurrencyPair;

@AutoValue
abstract class CurrencyPairSupply {
  static CurrencyPairSupply create(ImmutableList<CurrencyPairMetadata> metadataList) {
    return new AutoValue_CurrencyPairSupply(metadataList);
  }

  abstract ImmutableList<CurrencyPairMetadata> metadataList();

  ImmutableList<CurrencyPair> currencyPairs() {
    return metadataList()
      .stream()
      .map(CurrencyPairMetadata::currencyPair) // Extract the CurrencyPair from each metadata.
      .collect(toImmutableList());
  }

  ImmutableList<String> symbols() {
    return currencyPairs()
      .stream()
      .map(CurrencyPair::symbol)
      .collect(toImmutableList());
  }
}
