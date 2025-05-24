package com.verlumen.tradestream.instruments;

import java.io.Serializable;

record CoinMarketCapConfig(int topN, String apiKey) implements Serializable {
  static CoinMarketCapConfig create(int topN, String apiKey) {
    return new CoinMarketCapConfig(topN, apiKey);
  }
}
