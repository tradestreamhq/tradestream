package com.verlumen.tradestream.marketdata;

import static com.google.protobuf.util.Timestamps.fromMillis;

import com.google.auto.value.AutoValue;
import com.google.common.collect.ImmutableList;
import com.google.inject.AbstractModule;
import com.google.inject.Key;
import com.google.inject.Provider;
import com.google.inject.Provides;
import com.google.inject.Singleton;
import com.google.inject.assistedinject.FactoryModuleBuilder;
import com.verlumen.tradestream.execution.RunMode;

@AutoValue
public abstract class MarketDataModule extends AbstractModule {
  public static MarketDataModule create(String exchangeName, Duration granularity, RunMode runMode, String tiingoApiKey) {
    return new AutoValue_MarketDataModule(exchangeName, granularity, runMode, tiingoApiKey);
  }

  abstract String exchangeName();
  abstract Duration granularity();
  abstract RunMode runMode();
  abstract String tiingoApiKey();

  @Override
  protected void configure() {
    bind(CandleSource.class).to(TradeBackedCandleSource.class);
    bind(ExchangeClientUnboundedSource.class).to(ExchangeClientUnboundedSourceImpl.class);
    bind(ExchangeStreamingClient.Factory.class).to(ExchangeStreamingClientFactory.class);

    // Install FactoryModuleBuilder for FillForwardCandlesFn (NEW)
    install(new FactoryModuleBuilder()
        .build(FillForwardCandlesFn.Factory.class));

    // Install FactoryModuleBuilder for FillForwardCandles PTransform (NEW)
    install(new FactoryModuleBuilder()
        .implement(FillForwardCandles.class, FillForwardCandles.class)
        .build(FillForwardCandles.Factory.class));
    // Install FactoryModuleBuilder for TradeToCandle
    install(new FactoryModuleBuilder()
        .implement(TradeToCandle.class, TradeToCandle.class)
        .build(TradeToCandle.Factory.class));
  }

  @Provides
  @Singleton
  CandleSource provideCandleSource(
      Provider<TradeBackedCandleSource> tradeBackedCandleSource,
      TiingoCryptoCandleSource.Factory tiingoCryptoCandleSourceFactory,
      RunMode runMode) {
    
      switch (runMode) {
          case DRY: 
              return tradeBackedCandleSource.get();
          case WET:
              return tiingoCryptoCandleSourceFactory.create(candleDuration(), tiingoApiKey());
          default: 
              throw new UnsupportedOperationException("Unsupported RunMode: " + runMode);
      }
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
          .setTimestamp(fromMillis(1259999L))
          .setPrice(50000.0)
          .setVolume(0.1)
          .build()));
      default: throw new UnsupportedOperationException("Unsupported RunMode: " + runMode());
    }
  }
}
