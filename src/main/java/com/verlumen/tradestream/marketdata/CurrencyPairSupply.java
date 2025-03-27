package com.verlumen.tradestream.marketdata;

import com.google.common.collect.ImmutableList;
import com.verlumen.tradestream.instruments.CurrencyPair;

interface CurrencyPairSupply extends Supplier<ImmutableList<CurrencyPair>> {}
