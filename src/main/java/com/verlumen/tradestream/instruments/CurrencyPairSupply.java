package com.verlumen.tradestream.instruments;

import com.google.common.collect.ImmutableList;
import java.io.Serializable;
import java.util.function.Supplier;

public interface CurrencyPairSupply extends Serializable, Supplier<ImmutableList<CurrencyPair>> {
  default ImmutableList<CurrencyPair> currencyPairs() {
    return get();
  }
}
