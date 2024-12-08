package com.verlumen.tradestream.ingestion;

import com.google.common.collect.ImmutableList;

interface CurrencyPairSupply {
  ImmutableList<CurrencyPairMetadata> metadataList();
}
