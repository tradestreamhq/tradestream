package com.verlumen.tradestream.pipeline;

import com.google.inject.Guice;
import com.google.inject.Inject;
import com.verlumen.tradestream.kafka.KafkaReadTransform;
import java.util.Arrays;
import org.apache.beam.sdk.Pipeline;
import org.apache.beam.sdk.options.Default;
import org.apache.beam.sdk.options.Description;
import org.apache.beam.sdk.options.PipelineOptionsFactory;
import org.apache.beam.sdk.options.StreamingOptions;
import org.apache.beam.sdk.transforms.Create;
import org.apache.beam.sdk.transforms.MapElements;
import org.apache.beam.sdk.values.PCollection;
import org.apache.beam.sdk.values.TypeDescriptors;

final class App {
  public interface Options extends StreamingOptions {
    @Description("Comma-separated list of Kafka bootstrap servers.")
    @Default.String("localhost:9092") 
    String getBootstrapServers();
    void setBootstrapServers(String value);

    @Description("Kafka topic to read candle data from.")
    @Default.String("candles")
    String getCandleTopic();
    void setCandleTopic(String value);

    @Description("Interval in hours for dynamic read.")
    @Default.Integer(1) // Default to 1 hour
    int getDynamicReadIntervalHours();
    void setDynamicReadIntervalHours(int value);
  }

  private final KafkaReadTransform kafkaReadTransform;

  @Inject
  App(KafkaReadTransform kafkaReadTransform) {
    this.kafkaReadTransform = kafkaReadTransform;
  }

  PCollection<String> buildPipeline(Pipeline pipeline) {
    return pipeline
        .apply("Create elements", kafkaReadTransform)
        .apply(
            "Print elements",
            MapElements.into(TypeDescriptors.strings())
                .via(
                    x -> {
                      System.out.println(x);
                      return x;
                    }));
  }

  void runPipeline(Pipeline pipeline) {
    buildPipeline(pipeline);
    pipeline.run().waitUntilFinish();
  }

  public static void main(String[] args) {
    var options = PipelineOptionsFactory.fromArgs(args).withValidation().as(Options.class);
    var module = PipelineModule.create(
      options.getBootstrapServers(),
      options.getCandleTopic(),
      options.getDynamicReadIntervalHours());
    var app = Guice.createInjector(module).getInstance(App.class);
    var pipeline = Pipeline.create(options);
    app.runPipeline(pipeline);
  }
}
