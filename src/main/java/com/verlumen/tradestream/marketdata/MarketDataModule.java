package com.verlumen.tradestream.marketdata;

import com.google.inject.AbstractModule;
import com.google.inject.assistedinject.FactoryModuleBuilder;

public final class MarketDataModule extends AbstractModule {
  public static MarketDataModule create() {
    return new MarketDataModule();
  }

  private MarketDataModule() {}

  @Override
  protected void configure() {
    bind(CreateCandles.class).toProvider(CreateCandles::create);

    install(
        new FactoryModuleBuilder()
            .implement(TradePublisher.class, TradePublisherImpl.class)
            .build(TradePublisher.Factory.class));
  }
}
