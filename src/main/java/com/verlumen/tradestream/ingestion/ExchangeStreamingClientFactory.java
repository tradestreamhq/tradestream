package com.verlumen.tradestream.ingestion;

import static com.google.common.base.Preconditions.checkArgument;
import static com.google.common.base.Strings.isNullOrEmpty;

import com.google.common.collect.ImmutableMap;
import com.google.inject.Inject;
import com.google.inject.Provider;
import com.verlumen.tradestream.marketdata.Trade;

import java.util.function.Consumer;

final class ExchangeStreamingClientFactory implements ExchangeStreamingClient.Factory {
  private final ImmutableMap<String, Provider<ExchangeStreamingClient>> clientMap;

  @Inject
  ExchangeStreamingClient(Provider<CoinbaseStreamingClient> coinbaseStreamingClient) {
    this.clientMap = ImmutableMap.builder()
      .put("coinbase", coinbaseStreamingClient)
      .buildOrThrow();
  }

  @Override
  public ExchangeStreamingClient create(String exchangeName) {
    checkArgument(clientMap.contains(exchangeName));
    return clientMap.get(exchangeName).get();
  }
}
