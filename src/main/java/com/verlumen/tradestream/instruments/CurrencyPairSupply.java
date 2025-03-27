package com.verlumen.tradestream.instruments;

import com.google.common.collect.ImmutableList;
import com.verlumen.tradestream.instruments.CurrencyPair;
import java.util.function.Supplier;

interface CurrencyPairSupply extends Supplier<ImmutableList<CurrencyPair>> {}
