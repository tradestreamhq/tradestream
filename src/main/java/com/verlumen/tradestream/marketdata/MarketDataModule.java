package com.verlumen.tradestream.marketdata;

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

  abstract String exchangeName();
  abstract RunMode runMode();

  @Override
  protected void configure() {
    bind(ExchangeClientUnboundedSource.class).to(ExchangeClientUnboundedSourceImpl.class);
    bind(ExchangeStreamingClient.Factory.class).to(ExchangeStreamingClientFactory.class);

    install(new FactoryModuleBuilder()
        .implement(CandleCreatorFn.class, CandleCreatorFn.class)
        .build(CandleCreatorFn.Factory.class));

    install(new FactoryModuleBuilder()
        .implement(TradeToCandle.class, TradeToCandle.class)
        .build(TradeToCandle.Factory.class));
  }

  @Provides
  @Singleton
  ExchangeStreamingClient provideExchangeStreamingClient(
      ExchangeStreamingClient.Factory factory) {
    return factory.create(exchangeName());
  }

  @Provides
  @Singleton
  TradeSource provideTradeSource(Provider<ExchangeClientTradeSource> exchangeClientTradeSource) {
    switch (runMode()) {
      case DRY: return DryRunTradeSource.create(
        ImmutableList.of(
          Trade.newBuilder()
          .setExchange(exchangeName())
          .setCurrencyPair("DRY/RUN")
          .setTradeId("trade-123")
          .setTimestamp(fromMillis(1234567))
          .setPrice(50000.0)
          .setVolume(0.1)
          .build()));
      case WET: return exchangeClientTradeSource.get();
      default: throw new UnsupportedOperationException();
    }
  }
}
