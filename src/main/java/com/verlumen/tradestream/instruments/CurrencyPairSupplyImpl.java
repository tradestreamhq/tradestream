package com.verlumen.tradestream.instruments;

import static com.google.common.collect.ImmutableList.toImmutableList;

import com.google.common.collect.ImmutableList;

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
