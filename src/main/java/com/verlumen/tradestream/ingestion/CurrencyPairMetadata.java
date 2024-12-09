package com.verlumen.tradestream.ingestion;

import com.google.auto.value.AutoValue;
import org.knowm.xchange.currency.Currency;
import org.knowm.xchange.currency.CurrencyPair;

import java.math.BigDecimal;

@AutoValue
abstract class CurrencyPairMetadata {
  static CurrencyPairMetadata create(String pair, BigDecimal marketCapValue) {
    return create(new CurrencyPair(pair), marketCapValue);
  }

  static CurrencyPairMetadata create(CurrencyPair currencyPair, long marketCapValue) {
    return create(currencyPair, BigDecimal.valueOf(marketCapValue));
  }

  private static CurrencyPairMetadata create(CurrencyPair currencyPair, BigDecimal marketCap) {
    return new AutoValue_CurrencyPairMetadata(currencyPair, marketCap);
  }

  abstract CurrencyPair currencyPair();

  abstract BigDecimal marketCap();
}
