package com.verlumen.tradestream.marketdata;

import com.google.auto.value.AutoValue;
import com.google.inject.AbstractModule;
import com.google.inject.Provides;
import com.google.inject.assistedinject.FactoryModuleBuilder;

@AutoValue
public abstract class MarketDataModule extends AbstractModule {
  public static MarketDataModule create(MarketDataConfig config) {
    return new AutoValue_MarketDataModule(config);
  }

  abstract MarketDataConfig config();

  @Override
  protected void configure() {
    bind(ExchangeClientUnboundedSource.class).to(ExchangeClientUnboundedSourceImpl.class);
    bind(ExchangeStreamingClient.Factory.class).to(ExchangeStreamingClientFactory.class);

    install(new FactoryModuleBuilder()
            .implement(ExchangeClientUnboundedReader.class, ExchangeClientUnboundedReaderImpl.class)
            .build(ExchangeClientUnboundedReader.Factory.class));
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
