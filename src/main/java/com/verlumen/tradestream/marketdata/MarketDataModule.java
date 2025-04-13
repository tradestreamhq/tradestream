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

    install(FactoryModuleBuilder()
        .implement(CandleCreatorFn::class.java, CandleCreatorFn::class.java)
        .build(CandleCreatorFn.Factory::class.java));

    install(FactoryModuleBuilder()
        .implement(TradeToCandle::class.java, TradeToCandle::class.java)
        .build(TradeToCandle.Factory::class.java));
  }

  @Provides
  ExchangeStreamingClient provideExchangeStreamingClient(
      ExchangeStreamingClient.Factory exchangeStreamingClientFactory) {
    return exchangeStreamingClientFactory.create(exchangeName());
  }

  @Provides
  @Singleton
  TradeSource provideTradeSource(Provider<ExchangeClientTradeSource> exchangeClientTradeSource) {
    switch (runMode()) {
      case DRY: return DryRunTradeSource.create(ImmutableList.of(DRY_RUN_TRADE));
      case WET: return exchangeClientTradeSource.get();
      default: throw new UnsupportedOperationException();
    }
  }
}
