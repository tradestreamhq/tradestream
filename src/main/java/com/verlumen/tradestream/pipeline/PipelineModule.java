package com.verlumen.tradestream.pipeline;

import static com.google.protobuf.util.Timestamps.fromMillis;

import com.google.auto.value.AutoValue;
import com.google.inject.AbstractModule;
import com.google.inject.Provides;
import com.verlumen.tradestream.backtesting.BacktestingModule;
import com.verlumen.tradestream.execution.RunMode;
import com.verlumen.tradestream.kafka.KafkaModule;
import com.verlumen.tradestream.marketdata.Trade;
import com.verlumen.tradestream.signals.SignalsModule;
import com.verlumen.tradestream.strategies.StrategiesModule;
import com.verlumen.tradestream.ta4j.Ta4jModule;
import java.nio.charset.StandardCharsets;
import org.apache.kafka.common.serialization.ByteArrayDeserializer;
import org.apache.kafka.common.serialization.StringDeserializer;

@AutoValue
abstract class PipelineModule extends AbstractModule {
  static PipelineModule create(PipelineConfig config) {
    return new AutoValue_PipelineModule(config);
  }

  abstract PipelineConfig config();

  @Override
  protected void configure() {
      install(BacktestingModule.create());
      install(KafkaModule.create(config().bootstrapServers()));
      install(MarketDataModule.create());
      install(SignalsModule.create(config().signalTopic()));
      install(StrategiesModule.create());
      install(Ta4jModule.create());
  }

  @Provides
  PipelineConfig providePipelineConfig() {
    return config();
  }
}
