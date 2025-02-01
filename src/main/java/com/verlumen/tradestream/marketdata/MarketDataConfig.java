package com.verlumen.tradestream.marketdata;

public record MarketDataConfig(String tradeTopic) {
  public static MarketDataConfig create(String tradeTopic) {
    return new MarketDataConfig(tradeTopic);
  }
}
