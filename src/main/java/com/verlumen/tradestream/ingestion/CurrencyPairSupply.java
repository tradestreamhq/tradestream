package com.verlumen.tradestream.ingestion;

import com.google.common.collect.ImmutableList;
import com.verlumen.tradestream.instruments.CurrencyPair;

interface CurrencyPairSupply extends Supplier<ImmutableList<CurrencyPair>> {}
