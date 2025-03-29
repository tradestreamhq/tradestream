package com.verlumen.tradestream.pipeline;

import com.google.auto.value.AutoValue;
import com.google.inject.AbstractModule;
import com.google.inject.Provides;
import com.google.inject.Singleton;
import com.verlumen.tradestream.backtesting.BacktestingModule;
import com.verlumen.tradestream.execution.ExecutionModule;
import com.verlumen.tradestream.execution.RunMode;
import com.verlumen.tradestream.marketdata.DryRunExchangeClientUnboundedSource;
import com.verlumen.tradestream.marketdata.ExchangeClientUnboundedSource;
import com.verlumen.tradestream.marketdata.ExchangeClientUnboundedSourceImpl;
import com.verlumen.tradestream.marketdata.MarketDataModule;
import com.verlumen.tradestream.signals.SignalsModule;
import com.verlumen.tradestream.strategies.StrategiesModule;
import com.verlumen.tradestream.ta4j.Ta4jModule;

@AutoValue
abstract class PipelineModule extends AbstractModule {
  static PipelineModule create(PipelineConfig config) {
    return new AutoValue_PipelineModule(config);
  }

  abstract PipelineConfig config();

  @Override
  protected void configure() {
      install(BacktestingModule.create());
      install(ExecutionModule.create(config().runMode()));
      // Install MarketDataModule - provides dependencies for ExchangeClientUnboundedSourceImpl
      install(MarketDataModule.create("coinbase", config().tradeTopic()));
      install(SignalsModule.create(config().signalTopic()));
      install(StrategiesModule.create());
      install(Ta4jModule.create());
  }

  @Provides
  @Singleton
  ExchangeClientUnboundedSource provideExchangeClientUnboundedSource(
      RunMode runMode,
      Provider<DryRunExchangeClientUnboundedSource> fakeSourceProvider,
      Provider<ExchangeClientUnboundedSourceImpl> realSourceProvider) {
    if (runMode.equals(RunMode.DRY)) {
      return fakeSourceProvider.get();
    }

    // Get an instance of the real source implementation via its provider
    return realSourceProvider.get();
  }

  @Provides
  PipelineConfig providePipelineConfig() {
    return config();
  }
}
