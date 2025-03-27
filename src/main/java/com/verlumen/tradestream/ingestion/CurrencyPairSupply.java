package com.verlumen.tradestream.ingestion;

import static com.google.common.collect.ImmutableList.toImmutableList;

import com.google.common.collect.ImmutableList;
import com.verlumen.tradestream.instruments.CurrencyPair;

record CurrencyPairSupply(ImmutableList<CurrencyPairMetadata> metadataList) {
  static CurrencyPairSupply create(ImmutableList<CurrencyPairMetadata> metadataList) {
    return new CurrencyPairSupply(metadataList);
  }

  ImmutableList<CurrencyPair> currencyPairs() {
    return metadataList()
      .stream()
      .map(CurrencyPairMetadata::currencyPair)
      .collect(toImmutableList());
  }
}
