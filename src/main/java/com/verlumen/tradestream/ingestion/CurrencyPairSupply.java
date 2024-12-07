package com.verlumen.tradestream.ingestion;

import static com.google.common.collect.ImmutableList.toImmutableList;

import com.google.common.collect.ImmutableList;
import org.knowm.xchange.currency.CurrencyPair;

interface CurrencyPairSupply {
  ImmutableList<CurrencyPairMetadata> metadataList();
  
  default ImmutableList<String> symbols() {
    return currencyPairs()
      .stream()
      .map(pair -> pair.getBase() + "-" + pair.getCounter())
      .collect(toImmutableList());
  }
}
