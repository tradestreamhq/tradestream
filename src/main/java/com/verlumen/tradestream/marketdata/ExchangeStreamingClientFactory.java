package com.verlumen.tradestream.marketdata;

import static com.google.common.base.Preconditions.checkArgument;
import static com.google.common.base.Strings.isNullOrEmpty;

import com.google.common.collect.ImmutableMap;
import com.google.inject.Inject;
import com.google.inject.Provider;

final class ExchangeStreamingClientFactory implements ExchangeStreamingClient.Factory {
  private final ImmutableMap<String, Provider<? extends ExchangeStreamingClient>> clientMap;

  @Inject
  ExchangeStreamingClientFactory(Provider<CoinbaseStreamingClient> coinbaseStreamingClient) {
    this.clientMap = ImmutableMap.<String, Provider<? extends ExchangeStreamingClient>>builder()
      .put("coinbase", coinbaseStreamingClient)
      .buildOrThrow();
  }

  @Override
  public ExchangeStreamingClient create(String exchangeName) {
    checkArgument(clientMap.containsKey(exchangeName), "Unsupported exchange: " + exchangeName);
    return clientMap.get(exchangeName).get();
  }
}
