package com.verlumen.tradestream.instruments;

import com.google.common.collect.ImmutableList;
import java.util.function.Supplier;

interface CurrencyPairSupply extends Supplier<ImmutableList<CurrencyPair>> {
  default ImmutableList<CurrencyPair> currencyPairs() {
    return get();
  }
}
