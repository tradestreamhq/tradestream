package com.verlumen.tradestream.marketdata;

import com.google.auto.value.AutoValue;
import com.google.inject.AbstractModule;
import com.google.inject.Provides;
import com.google.inject.assistedinject.FactoryModuleBuilder;

public class MarketDataModule extends AbstractModule {
  public static MarketDataModule create() {
    switch(config().runMode()) {
      case DRY: return DryRunModule.create();
      case WET: return ProdModule.create(config().exchangeName());
      default: throw new UnsupportedOperationException();
    }    
  }

  @AutoValue
  abstract static class ProdModule extends MarketDataModule {
    public static ProdModule create(String exchangeName) {
      return new AutoValue_MarketDataModule_ProdModule(exchangeName);
    }

    abstract String exchangeName();

    @Override
    protected void configure() {
      bind(ExchangeClientUnboundedSource.class).to(ExchangeClientUnboundedSourceImpl.class);
      bind(ExchangeStreamingClient.Factory.class).to(ExchangeStreamingClientFactory.class);

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

  static class DryRunModule extends MarketDataModule {
    public static DryRunModule create() {
      return new DryRunModule();
    }

    @Override
    protected void configure() {
      bind(ExchangeClientUnboundedReader.class).to(DryRunExchangeClientUnboundedReader.class);
      bind(ExchangeClientUnboundedSource.class).to(DryRunExchangeClientUnboundedSource.class);
    }
  }
}
