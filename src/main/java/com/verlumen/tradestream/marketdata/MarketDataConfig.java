package com.verlumen.tradestream.marketdata;

public record MarketDataConfig(String exchangeName, String tradeTopic) {
  public static MarketDataConfig create(String exchangeName, String tradeTopic) {
    return new MarketDataConfig(exchangeName, tradeTopic);
  }
}
