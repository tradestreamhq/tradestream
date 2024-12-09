package com.verlumen.tradestream.ingestion;

import com.google.auto.value.AutoValue;
import com.verlumen.tradestream.instruments.Currency;
import com.verlumen.tradestream.instruments.CurrencyPair;

import java.math.BigDecimal;

@AutoValue
abstract class CurrencyPairMetadata {
  static CurrencyPairMetadata create(String symbol, BigDecimal marketCapValue) {
    return create(CurrencyPair.fromSymbol(symbol), marketCapValue);
  }

  private static CurrencyPairMetadata create(CurrencyPair currencyPair, BigDecimal marketCap) {
    return new AutoValue_CurrencyPairMetadata(currencyPair, marketCap);
  }

  abstract CurrencyPair currencyPair();

  abstract BigDecimal marketCap();
}
