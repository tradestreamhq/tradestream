package com.verlumen.tradestream.ingestion;

import static com.google.common.collect.ImmutableList.toImmutableList;

import com.google.auto.value.AutoValue;
import com.google.common.collect.ImmutableList;
import org.knowm.xchange.currency.CurrencyPair;

@AutoValue
abstract class CurrencyPairSupply {
  static CurrencyPairSupply create(ImmutableList<CurrencyPairMetadata> metadataList) {
    return new AutoValue_CurrencyPairSupply(metadataList);
  }

  abstract ImmutableList<CurrencyPairMetadata> metadataList();
  
  ImmutableList<CurrencyPair> currencyPairs() {
    return metadataList()
      .stream()
      .map(CurrencyPairMetadata::currencyPair)
      .collect(toImmutableList());
  }
}