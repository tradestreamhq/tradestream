package com.verlumen.tradestream.marketdata;

import com.google.inject.AbstractModule;

public final class MarketDataModule extends AbstractModule {
  public static MarketDataModule create() {
    return new MarketDataModule();
  }

  private MarketDataModule() {}

  @Override
  protected void configure() {
    install(
        new FactoryModuleBuilder()
            .implement(TradePublisher.class, TradePublisherImpl.class)
            .build(TradePublisher.Factory.class));
  }
}
