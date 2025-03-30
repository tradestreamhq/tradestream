package com.verlumen.tradestream.pipeline;

import com.google.auto.value.AutoValue;
import com.google.inject.AbstractModule;
import com.google.inject.Provider;
import com.google.inject.Provides;
import com.google.inject.Singleton;
import com.verlumen.tradestream.backtesting.BacktestingModule;
import com.verlumen.tradestream.execution.RunMode;
import com.verlumen.tradestream.kafka.KafkaModule;
import com.verlumen.tradestream.marketdata.MarketDataModule;
import com.verlumen.tradestream.signals.SignalsModule;
import com.verlumen.tradestream.strategies.StrategiesModule;
import com.verlumen.tradestream.ta4j.Ta4jModule;

@AutoValue
abstract class PipelineModule extends AbstractModule {
  private static final Trade DRY_RUN_TRADE = Trade.newBuilder()
      .setExchange("FakeExhange")
      .setCurrencyPair("DRY/RUN")
      .setTradeId("trade-123")
      .setTimestamp(fromMillis(1234567))
      .setPrice(50000.0)
      .setVolume(0.1)
      .build();

  static PipelineModule create(
    String bootstrapServers, String signalTopic, String tradeTopic, RunMode runMode) {
    return new AutoValue_PipelineModule(bootstrapServers, signalTopic, tradeTopic, runMode);
  }

  abstract String bootstrapServers();
  abstract String signalTopic();
  abstract String tradeTopic();
  abstract RunMode runMode();

  @Override
  protected void configure() {
      install(BacktestingModule.create());
      install(KafkaModule.create(config().bootstrapServers()));
      install(marketDataModule());
      install(SignalsModule.create(config().signalTopic()));
      install(StrategiesModule.create());
      install(Ta4jModule.create());
  }

  private MarketDataModule marketDataModule() {
    return MarketDataModule.create();
  }

  @Provides
  TimingConfig provideTimingConfig() {
    return TimingConfig.create();
  }
}
