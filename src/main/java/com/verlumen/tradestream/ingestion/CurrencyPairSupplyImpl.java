package com.verlumen.tradestream.ingestion;

import static com.google.common.collect.ImmutableList.toImmutableList;

import com.google.auto.value.AutoValue;
import com.google.common.collect.ImmutableList;
import org.knowm.xchange.currency.CurrencyPair;

@AutoValue
abstract class CurrencyPairSupplyImpl implements CurrencyPairSupply {
  static CurrencyPairSupplyImpl create(ImmutableList<CurrencyPairMetadata> metadataList) {
    return new AutoValue_CurrencyPairSupplyImpl(metadataList);
  }

  abstract ImmutableList<CurrencyPairMetadata> metadataList();
}
