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

  abstract String exchangeName();
  abstract RunMode runMode();

  @Override
  protected void configure() {
    bind(ExchangeClientUnboundedSource.class).to(ExchangeClientUnboundedSourceImpl.class);
    bind(ExchangeStreamingClient.Factory.class).to(ExchangeStreamingClientFactory.class);

    // Bind CandleCreatorFn as it's used by the stateful TradeToCandle
    bind(CandleCreatorFn.class);

    // Remove binding for CandleCombineFn if it was only for the Combine.perKey approach
    // If CandleCombineFn is used elsewhere, keep its binding.
    // For this revert, assuming it's not needed elsewhere:
    // tryUnbind(Key.get(SlidingCandleAggregator.CandleCombineFn.class)); // Or just remove the bind() call if added manually

    // Install FactoryModuleBuilder for TradeToCandle (which now depends on CandleCreatorFn)
    install(new FactoryModuleBuilder()
        .implement(TradeToCandle.class, TradeToCandle.class)
        .build(TradeToCandle.Factory.class));

    // Remove factories related to the separate FillForward transform if they were added
    // tryUnbind(Key.get(FillForwardCandlesFn.Factory.class));
    // tryUnbind(Key.get(FillForwardCandles.Factory.class));
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
      default: throw new UnsupportedOperationException("Unsupported RunMode: " + runMode());
    }
  }
}
