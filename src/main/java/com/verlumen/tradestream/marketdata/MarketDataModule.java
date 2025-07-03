package com.verlumen.tradestream.marketdata;

import com.google.inject.AbstractModule;
import com.google.inject.assistedinject.FactoryModuleBuilder;

public class MarketDataModule extends AbstractModule {

  public static MarketDataModule create() {
    return new MarketDataModule();
  }

  @Override
  protected void configure() {
    install(new FactoryModuleBuilder().build(FillForwardCandlesFn.Factory.class));
    install(
        new FactoryModuleBuilder()
            .implement(FillForwardCandles.class, FillForwardCandles.class)
            .build(FillForwardCandles.Factory.class));
    install(
        new FactoryModuleBuilder()
            .implement(InfluxDbCandleFetcher.class, InfluxDbCandleFetcher.class)
            .build(InfluxDbCandleFetcher.Factory.class));
    install(
        new FactoryModuleBuilder()
            .implement(TiingoCryptoCandleSource.class, TiingoCryptoCandleSource.class)
            .build(TiingoCryptoCandleSource.Factory.class));
    install(
        new FactoryModuleBuilder()
            .implement(TiingoCryptoCandleTransform.class, TiingoCryptoCandleTransform.class)
            .build(TiingoCryptoCandleTransform.Factory.class));
    install(new FactoryModuleBuilder().build(TiingoCryptoFetcherFn.Factory.class));
  }
}
