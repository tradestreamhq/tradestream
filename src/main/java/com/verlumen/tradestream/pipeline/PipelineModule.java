package com.verlumen.tradestream.pipeline;

import static com.google.protobuf.util.Timestamps.fromMillis;

import com.google.auto.value.AutoValue;
import com.google.inject.AbstractModule;
import com.google.inject.Provides;
import com.verlumen.tradestream.backtesting.BacktestingModule;
import com.verlumen.tradestream.execution.RunMode;
import com.verlumen.tradestream.http.HttpModule;
import com.verlumen.tradestream.instruments.InstrumentsModule;
import com.verlumen.tradestream.kafka.KafkaModule;
import com.verlumen.tradestream.marketdata.MarketDataModule;
import com.verlumen.tradestream.signals.SignalsModule;
import com.verlumen.tradestream.strategies.StrategiesModule;
import com.verlumen.tradestream.ta4j.Ta4jModule;

@AutoValue
abstract class PipelineModule extends AbstractModule {
  static PipelineModule create(
    String bootstrapServers,
    String coinMarketCapApiKey,
    String exchangeName,
    RunMode runMode,
    String signalTopic,
    int topCurrencyCount) {
    return new AutoValue_PipelineModule(
      bootstrapServers, coinMarketCapApiKey, exchangeName, runMode, signalTopic, topCurrencyCount);
  }

  abstract String bootstrapServers();
  abstract String coinMarketCapApiKey();
  abstract String exchangeName();
  abstract RunMode runMode();
  abstract String signalTopic();
  abstract int topCurrencyCount();

  @Override
  protected void configure() {
      install(BacktestingModule.create());
      install(HttpModule.create());
      install(InstrumentsModule.create(runMode(), coinMarketCapApiKey(), topCurrencyCount()));
      install(KafkaModule.create(bootstrapServers()));
      install(MarketDataModule.create(exchangeName(), runMode()));
      install(SignalsModule.create(signalTopic()));
      install(StrategiesModule.create());
      install(Ta4jModule.create());
  }

  @Provides
  TimingConfig provideTimingConfig() {
    return TimingConfig.create();
  }
}
