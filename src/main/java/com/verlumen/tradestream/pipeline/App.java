package com.verlumen.tradestream.pipeline;

import com.google.inject.Guice;
import com.google.inject.Inject;
import com.verlumen.tradestream.kafka.KafkaReadTransform;
import com.verlumen.tradestream.marketdata.CreateCandles;
import com.verlumen.tradestream.marketdata.ParseTrades;
import org.apache.beam.runners.flink.FlinkPipelineOptions;
import org.apache.beam.sdk.Pipeline;
import org.apache.beam.sdk.options.Default;
import org.apache.beam.sdk.options.Description;
import org.apache.beam.sdk.options.PipelineOptionsFactory;
import org.apache.beam.sdk.options.StreamingOptions;
import org.apache.beam.sdk.values.PCollection;

public final class App {
  public interface Options extends StreamingOptions {
    @Description("Comma-separated list of Kafka bootstrap servers.")
    @Default.String("localhost:9092")
    String getBootstrapServers();

    void setBootstrapServers(String value);

    @Description("Kafka topic to read trade data from.")
    @Default.String("trades")
    String getTradeTopic();

    void setTradeTopic(String value);

    @Description("Run mode: wet or dry.")
    @Default.String("wet")
    String getRunMode();

    void setRunMode(String value);
  }

  private final CreateCandles createCandles;
  private final KafkaReadTransform<String, byte[]> kafkaReadTransform;
  private final ParseTrades parseTrades;

  @Inject
  App(
      CreateCandles createCandles,
      KafkaReadTransform<String, byte[]> kafkaReadTransform,
      ParseTrades parseTrades) {
    this.createCandles = createCandles;
    this.kafkaReadTransform = kafkaReadTransform;
    this.parseTrades = parseTrades;
  }

  private Pipeline buildPipeline(Pipeline pipeline) {
    PCollection<byte[]> input = pipeline.apply("Read from Kafka", kafkaReadTransform);

    input.apply("Parse Trades", parseTrades);

    return pipeline;
  }

  private void runPipeline(Pipeline pipeline) {
    buildPipeline(pipeline);
    pipeline.run();
  }

  public static void main(String[] args) {
    // Parse custom options
    var options = PipelineOptionsFactory.fromArgs(args).withValidation().as(Options.class);

    // Convert to FlinkPipelineOptions and set required properties
    FlinkPipelineOptions flinkOptions = options.as(FlinkPipelineOptions.class);
    flinkOptions.setAttachedMode(false);
    flinkOptions.setStreaming(true);

    var module =
        PipelineModule.create(
            options.getBootstrapServers(), options.getTradeTopic(), options.getRunMode());
    var app = Guice.createInjector(module).getInstance(App.class);
    var pipeline = Pipeline.create(options);
    app.runPipeline(pipeline);
  }
}
