package com.verlumen.tradestream.pipeline;

import static com.google.protobuf.util.Timestamps.fromMillis;

import com.google.auto.value.AutoValue;
import com.google.inject.AbstractModule;
import com.google.inject.Provides;
import com.verlumen.tradestream.backtesting.BacktestingModule;
import com.verlumen.tradestream.execution.RunMode;
import com.verlumen.tradestream.kafka.DryRunKafkaReadTransform;
import com.verlumen.tradestream.kafka.KafkaModule;
import com.verlumen.tradestream.kafka.KafkaReadTransform;
import com.verlumen.tradestream.marketdata.Trade;
import com.verlumen.tradestream.signals.SignalsModule;
import com.verlumen.tradestream.strategies.StrategiesModule;
import com.verlumen.tradestream.ta4j.Ta4jModule;
import java.nio.charset.StandardCharsets;
import org.apache.kafka.common.serialization.ByteArrayDeserializer;
import org.apache.kafka.common.serialization.StringDeserializer;
import org.joda.time.Duration;

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

  static PipelineModule create(PipelineConfig config) {
    return new AutoValue_PipelineModule(config);
  }

  abstract PipelineConfig config();

  @Override
  protected void configure() {
      install(BacktestingModule.create());
      install(KafkaModule.create(config().bootstrapServers()));
      install(SignalsModule.create(config().signalTopic()));
      install(StrategiesModule.create());
      install(Ta4jModule.create());
  }

  @Provides
  KafkaReadTransform<String, byte[]> provideKafkaReadTransform(KafkaReadTransform.Factory factory) {
      if (config().runMode().equals(RunMode.DRY)) {
        return DryRunKafkaReadTransform
            .<String, byte[]>builder()
            .setBootstrapServers(config().bootstrapServers())
            .setTopic(config().tradeTopic())
            .setKeyDeserializerClass(StringDeserializer.class)
            .setValueDeserializerClass(ByteArrayDeserializer.class)
            .setDefaultValue(DRY_RUN_TRADE.toByteArray())
            .build();
      }

      return factory.create(
          config().tradeTopic(), 
          StringDeserializer.class,
          ByteArrayDeserializer.class);
  }

  @Provides
  PipelineConfig providePipelineConfig() {
    return config();
  }

  @Provides
  TimingConfig provideTimingConfig() {
    return TimingConfig.create();
  }
}
