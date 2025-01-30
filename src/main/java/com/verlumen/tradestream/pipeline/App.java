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

public final class App {
  public interface Options extends StreamingOptions {
    @Description("Comma-separated list of Kafka bootstrap servers.")
    @Default.String("localhost:9092") 
    String getBootstrapServers();
    void setBootstrapServers(String value);

    @Description("Kafka topic to read candle data from.")
    @Default.String("candles")
    String getCandleTopic();
    void setCandleTopic(String value);

    @Description("Run mode: wet or dry.")
    @Default.String("wet") // Default to "wet" mode
    String getRunMode();
    void setRunMode(String value);
  }

  private final KafkaReadTransform kafkaReadTransform;

  @Inject
  App(KafkaReadTransform kafkaReadTransform) {
    this.kafkaReadTransform = kafkaReadTransform;
  }

  static PCollection<String> buildPipeline(Pipeline pipeline) {
    return pipeline
        .apply("Create elements", Create.of(Arrays.asList("Hello", "World!")))
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
    App.buildPipeline(pipeline);
    pipeline.run().waitUntilFinish();
  }

  public static void main(String[] args) {
    var options = PipelineOptionsFactory.fromArgs(args).withValidation().as(Options.class);
    var module = PipelineModule.create(
      options.getBootstrapServers(),
      options.getCandleTopic(),
      options.getRunMode());
    var app = Guice.createInjector(module).getInstance(App.class);
    var pipeline = Pipeline.create(options);
    app.runPipeline(pipeline);
  }
}
