package com.verlumen.tradestream.ingestion;

import static com.google.common.collect.ImmutableList.toImmutableList;

import com.google.common.collect.ImmutableList;
import org.knowm.xchange.currency.CurrencyPair;

abstract CurrencyPairSupply {
  abstract ImmutableList<CurrencyPairMetadata> metadataList();
  
  ImmutableList<CurrencyPair> currencyPairs() {
    return metadataList()
      .stream()
      .map(CurrencyPairMetadata::currencyPair)
      .collect(toImmutableList());
  }
}
