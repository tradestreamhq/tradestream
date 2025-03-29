package com.verlumen.tradestream.marketdata;

import com.google.auto.value.AutoValue;
import com.google.inject.AbstractModule;
import com.google.inject.Provides;
import com.google.inject.assistedinject.FactoryModuleBuilder;

public class MarketDataModule extends AbstractModule {
  private static class BaseModule extends AbstractModule {
    @Override
    protected void configure() {
      bind(ExchangeClientUnboundedSource.class).to(ExchangeClientUnboundedSourceImpl.class);
    }
  }

  @AutoValue
  public abstract static class ProdModule extends AbstractModule {
    public static ProdModule create(String exchangeName) {
      return new AutoValue_MarketDataModule_ProdModule(exchangeName);
    }

    abstract String exchangeName();

    @Override
    protected void configure() {
      bind(ExchangeStreamingClient.Factory.class).to(ExchangeStreamingClientFactory.class);

      install(new BaseModule());
      install(new FactoryModuleBuilder()
              .implement(ExchangeClientUnboundedReader.class, ExchangeClientUnboundedReaderImpl.class)
              .build(ExchangeClientUnboundedReader.Factory.class));
    }

    @Provides
    ExchangeStreamingClient provideExchangeStreamingClient(
        ExchangeStreamingClient.Factory exchangeStreamingClientFactory) {
      return exchangeStreamingClientFactory.create(exchangeName());
    }
  }

  public static class DryRunModule extends AbstractModule {
    public static DryRunModule create() {
      return new DryRunModule();
    }

    @Override
    protected void configure() {
      bind(ExchangeClientUnboundedReader.class).to(DryRunExchangeClientUnboundedReader.class);
      bind(ExchangeClientUnboundedSource.class).to(DryRunExchangeClientUnboundedSource.class);

      install(new BaseModule());
    }
  }
}
