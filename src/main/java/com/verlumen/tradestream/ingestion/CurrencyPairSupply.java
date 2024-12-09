package com.verlumen.tradestream.ingestion;

import static com.google.common.collect.ImmutableList.toImmutableList;

import com.google.common.collect.ImmutableList;
import com.verlumen.tradestream.instruments.CurrencyPair;

interface CurrencyPairSupply {
  ImmutableList<CurrencyPairMetadata> metadataList();

  default ImmutableList<CurrencyPair> currencyPairs() {
    return metadataList()
      .stream()
      .map(CurrencyPairMetadata::currencyPair)
      .collect(toImmutableList());
  }

  default ImmutableList<String> symbols() {
    return currencyPairs()
      .stream()
      .map(CurrencyPair::symbol)
      .collect(toImmutableList());
  }
}
