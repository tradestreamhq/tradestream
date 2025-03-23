package com.verlumen.tradestream.ingestion;

record CoinMarketCapConfig(int topN, String apiKey) {
  static CoinMarketCapConfig create(int topN, String apiKey) {
      return new CoinMarketCapConfig(topN, apiKey);
  }
}
