package com.verlumen.tradestream.marketdata;

import com.google.inject.AbstractModule;
import com.google.inject.assistedinject.FactoryModuleBuilder;

/**
 * Guice module for market data components.
 */
public final class MarketDataModule extends AbstractModule {
  public static MarketDataModule create() {
    return new MarketDataModule();
  }

  @Override
  protected void configure() {
    bind(CandleFetcher.class).to(InfluxDbCandleFetcher.class);
    install(new FactoryModuleBuilder().build(FillForwardCandlesFn.Factory.class));
    install(
        new FactoryModuleBuilder()
            .implement(FillForwardCandles.class, FillForwardCandles.class)
            .build(FillForwardCandles.Factory.class));
    install(
        new FactoryModuleBuilder()
            .implement(TiingoCryptoCandleSource.class, TiingoCryptoCandleSource.class)
            .build(TiingoCryptoCandleSource.Factory.class));
    install(
        new FactoryModuleBuilder()
            .implement(TiingoCryptoCandleTransform.class, TiingoCryptoCandleTransform.class)
            .build(TiingoCryptoCandleTransform.Factory.class));
    install(new FactoryModuleBuilder().build(TiingoCryptoFetcherFn.Factory.class));
    install(
        new FactoryModuleBuilder()
            .implement(TradeToCandle.class, TradeToCandle.class)
            .build(TradeToCandle.Factory.class));
    install(new FactoryModuleBuilder().build(DryRunTradeSource.Factory.class));
    bind(CandleSourceFactory.class).to(CandleSourceFactoryImpl.class);
  }
}
