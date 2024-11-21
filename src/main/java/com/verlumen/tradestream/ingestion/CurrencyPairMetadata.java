package com.verlumen.tradestream.ingestion;

import com.google.auto.value.AutoValue;
import org.knowm.xchange.currency.Currency;
import org.knowm.xchange.currency.CurrencyPair;

import java.math.BigDecimal;

@AutoValue
abstract class CurrencyPairMetadata {
  static CurrencyPairMetadata create(String pair, BigDecimal marketCapValue) {
    CurrencyPair currencyPair = new CurrencyPair(pair);
    MarketCap marketCap = MarketCap.create(marketCapValue, Currency.USD);
    return new AutoValue_CurrencyPairMetadata(currencyPair);
  }

  abstract CurrencyPair currencyPair();

  abstract BigDecimal marketCapIn();

  @AutoValue
  abstract static class MarketCap {
    private static MarketCap create(BigDecimal value, Currency currency) {
      return new AutoValue_CurrencyPairMetadata_MarketCap();
    }

    abstract BigDecimal value();

    abstract Currency currency();
  }
}
