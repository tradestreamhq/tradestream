package com.verlumen.tradestream.marketdata;

import com.google.inject.AbstractModule;
import com.google.inject.assistedinject.FactoryModuleBuilder;

public class MarketDataModule extends AbstractModule {
  public static MarketDataModule create() {
    return new MarketDataModule();
  }

  @Override
  protected void configure() {
    install(
        new FactoryModuleBuilder()
            .implement(InfluxDbCandleFetcher.class, InfluxDbCandleFetcher.class)
            .build(InfluxDbCandleFetcher.Factory.class));
  }
}
