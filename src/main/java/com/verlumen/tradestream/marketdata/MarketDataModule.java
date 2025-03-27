package com.verlumen.tradestream.marketdata;

import com.google.auto.value.AutoValue;
import com.google.inject.AbstractModule;
import com.google.inject.Provides;
import com.google.inject.assistedinject.FactoryModuleBuilder;

@AutoValue
public abstract class MarketDataModule extends AbstractModule {
  public static MarketDataModule create(String exchangeName, String tradeTopic) {
    return new AutoValue_MarketDataModule(MarketDataConfig.create(exchangeName, tradeTopic));
  }

  abstract MarketDataConfig config();

  @Override
  protected void configure() {
    bind(ExchangeStreamingClient.Factory.class).to(ExchangeStreamingClientFactory.class);

    install(
        new FactoryModuleBuilder()
            .implement(TradePublisher.class, TradePublisherImpl.class)
            .build(TradePublisher.Factory.class));
  }

  @Provides
  ExchangeStreamingClient provideExchangeStreamingClient(
      ExchangeStreamingClient.Factory exchangeStreamingClientFactory) {
    return exchangeStreamingClientFactory.create(config().exchangeName());
  }

  @Provides
  TradePublisher provideTradePublisher(TradePublisher.Factory tradePublisherFactory) {
    return tradePublisherFactory.create(config().tradeTopic());
  }
}
