package com.verlumen.tradestream.marketdata;

import com.google.auto.value.AutoValue;
import com.google.inject.AbstractModule;
import com.google.inject.Provides;
import com.google.inject.assistedinject.FactoryModuleBuilder;

@AutoValue
public abstract class MarketDataModule extends AbstractModule {
  public static MarketDataModule create(String exchangeName, String tradeTopic) {
    return new AutoValue_MarketDataModule(exchangeName, tradeTopic);
  }

  abstract String exchangeName();
  abstract String tradeTopic();

  @Override
  protected void configure() {
    bind(ExchangeClientUnboundedSource.class).to(ExchangeClientUnboundedSourceImpl.class);
    bind(ExchangeStreamingClient.Factory.class).to(ExchangeStreamingClientFactory.class);
    bind(TradeSource.class).to(KafkaTradeSource.class);

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
    return exchangeStreamingClientFactory.create(exchangeName());
  }

  @Provides
  TradePublisher provideTradePublisher(TradePublisher.Factory tradePublisherFactory) {
    return tradePublisherFactory.create(tradeTopic());
  }
}
