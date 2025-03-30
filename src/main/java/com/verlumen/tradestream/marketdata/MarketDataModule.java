package com.verlumen.tradestream.marketdata;

import static com.google.protobuf.util.Timestamps.fromMillis;

import com.google.auto.value.AutoValue;
import com.google.common.collect.ImmutableList;
import com.google.inject.AbstractModule;
import com.google.inject.Provider;
import com.google.inject.Provides;
import com.google.inject.Singleton;
import com.google.inject.assistedinject.FactoryModuleBuilder;
import com.verlumen.tradestream.execution.RunMode;

@AutoValue
public abstract class MarketDataModule extends AbstractModule {
  public static MarketDataModule create(String exchangeName, RunMode runMode) {
    return new AutoValue_MarketDataModule(exchangeName, runMode);
  }

  private static final Trade DRY_RUN_TRADE = Trade.newBuilder()
      .setExchange("FakeExhange")
      .setCurrencyPair("DRY/RUN")
      .setTradeId("trade-123")
      .setTimestamp(fromMillis(1234567))
      .setPrice(50000.0)
      .setVolume(0.1)
      .build();

  abstract String exchangeName();
  abstract RunMode runMode();

  @Override
  protected void configure() {
    bind(ExchangeClientUnboundedSource.class).to(ExchangeClientUnboundedSourceImpl.class);
    bind(ExchangeStreamingClient.Factory.class).to(ExchangeStreamingClientFactory.class);

    install(new FactoryModuleBuilder()
            .implement(ExchangeClientUnboundedReader.class, ExchangeClientUnboundedReaderImpl.class)
            .build(ExchangeClientUnboundedReader.Factory.class));
    install(
        new FactoryModuleBuilder()
            .implement(TradePublisher.class, TradePublisherImpl.class)
            .build(TradePublisher.Factory.class));
  }

  @Provides
  ExchangeStreamingClient provideExchangeStreamingClient(
      ExchangeStreamingClient.Factory exchangeStreamingClientFactory) {
    return exchangeStreamingClientFactory.create(exchangeName());
  }

  @Provides
  @Singleton
  TradeSource provideTradeSource(Provider<ExchangeClientTradeSource> exchangeClientTradeSource) {
    if (runMode().equals(RunMode.DRY)) {
      return DryRunTradeSource.create(ImmutableList.of(DRY_RUN_TRADE));
    }

    return exchangeClientTradeSource.get();
  }
}
