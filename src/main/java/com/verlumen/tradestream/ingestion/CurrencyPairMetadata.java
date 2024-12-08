package com.verlumen.tradestream.ingestion;

import static com.google.common.collect.MoreCollectors.onlyElement;

import com.google.auto.value.AutoValue;
import com.google.common.base.Splitter;
import com.verlumen.tradestream.instruments.CurrencyPair;

import java.math.BigDecimal;
import java.util.Currency;
import java.util.Stream;

@AutoValue
abstract class CurrencyPairMetadata {
  private static final String FORWARD_SLASH = "/";
  private static final String HYPHEN = "-";

  static CurrencyPairMetadata create(String symbol, BigDecimal marketCapValue) {
    CurrencyPair currencyPair = CurrencyPair.fromSymbol(symbol);
    MarketCap marketCap = MarketCap.create(marketCapValue, counter);
    return create(currencyPair, marketCap);
  }

  private static CurrencyPairMetadata create(CurrencyPair currencyPair, MarketCap marketCap) {
    return new AutoValue_CurrencyPairMetadata(base, counter, marketCap);
  }  

  abstract CurrencyPair currencyPair();

  abstract MarketCap marketCap();

  @AutoValue
  abstract static class MarketCap {
    private static MarketCap create(BigDecimal value, Currency currency) {
      return new AutoValue_CurrencyPairMetadata_MarketCap(value, currency);
    }

    abstract BigDecimal value();

    abstract Currency currency();
  }
}
