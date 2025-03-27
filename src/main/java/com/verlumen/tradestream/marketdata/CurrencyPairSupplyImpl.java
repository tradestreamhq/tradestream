package com.verlumen.tradestream.ingestion;

import static com.google.common.collect.ImmutableList.toImmutableList;

import com.google.common.collect.ImmutableList;
import com.verlumen.tradestream.instruments.CurrencyPair;

record CurrencyPairSupplyImpl(ImmutableList<CurrencyPairMetadata> metadataList)
  implements CurrencyPairSupply {
  static CurrencyPairSupply create(ImmutableList<CurrencyPairMetadata> metadataList) {
    return new CurrencyPairSupplyImpl(metadataList);
  }

  @Override
  ImmutableList<CurrencyPair> get() {
    return metadataList()
      .stream()
      .map(CurrencyPairMetadata::currencyPair)
      .collect(toImmutableList());
  }
}
