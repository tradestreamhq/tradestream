package com.verlumen.tradestream.marketdata;

import com.google.inject.AbstractModule;
import com.google.inject.assistedinject.FactoryModuleBuilder;

@AutoValue
public final class MarketDataModule extends AbstractModule {
  public static MarketDataModule create(String tradeTopic) {
    return new AutoValue_MarketDataModule(tradeTopic);
  }

  abstract String tradeTopic();

  @Override
  protected void configure() {
    bind(CreateCandles.class).toProvider(CreateCandles::create);

    install(
        new FactoryModuleBuilder()
            .implement(TradePublisher.class, TradePublisherImpl.class)
            .build(TradePublisher.Factory.class));
  }

  @Provides
  TradePublisher provideTradePublisher(TradePublisher.Factory tradePublisherFactory) {
    return tradePublisherFactory.create(tradeTopic());
  }
}
