package com.verlumen.tradestream.pipeline;

import com.google.inject.Guice;
import com.google.inject.Inject;
import com.verlumen.tradestream.kafka.KafkaReadTransform;
import org.apache.beam.runners.flink.FlinkPipelineOptions;
import org.apache.beam.sdk.Pipeline;
import org.apache.beam.sdk.options.Default;
import org.apache.beam.sdk.options.Description;
import org.apache.beam.sdk.options.PipelineOptionsFactory;
import org.apache.beam.sdk.options.StreamingOptions;
import org.apache.beam.sdk.transforms.MapElements;
import org.apache.beam.sdk.values.KV;
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
        @Default.String("wet")
        String getRunMode();
        void setRunMode(String value);
    }

    private final KafkaReadTransform<String, byte[]> kafkaReadTransform;

    @Inject
    App(KafkaReadTransform<String, byte[]> kafkaReadTransform) {
        this.kafkaReadTransform = kafkaReadTransform;
    }

    private Pipeline buildPipeline(Pipeline pipeline) {
        pipeline
            .apply("Read from Kafka", kafkaReadTransform)
            .apply("Convert to String", 
                MapElements.<KV<String, byte[]>>into(TypeDescriptors.strings())
                    .via(kv -> {
                        String value = new String(kv.getValue());
                        System.out.println(value);
                        return value;
                    }));
        return pipeline;
    }

    public void runPipeline(Pipeline pipeline) {
        buildPipeline(pipeline);
        pipeline.run();
    }

    public static void main(String[] args) {
        // Parse custom options
        var options = PipelineOptionsFactory.fromArgs(args)
            .withValidation()
            .as(Options.class);

        // Convert to FlinkPipelineOptions and set required properties
        FlinkPipelineOptions flinkOptions = options.as(FlinkPipelineOptions.class);
        flinkOptions.setAttachedMode(false);
        flinkOptions.setStreaming(true);

        var module = PipelineModule.create(
            options.getBootstrapServers(),
            options.getCandleTopic(),
            options.getRunMode());
        var app = Guice.createInjector(module).getInstance(App.class);
        var pipeline = Pipeline.create(options);
        app.runPipeline(pipeline);
    }
}
