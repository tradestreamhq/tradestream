package com.verlumen.tradestream.pipeline;

import com.google.common.flogger.FluentLogger;
import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.kafka.KafkaReadTransform;
import com.verlumen.tradestream.marketdata.Candle;
import com.verlumen.tradestream.marketdata.CreateCandles;
import com.verlumen.tradestream.marketdata.ParseTrades;
import org.apache.beam.runners.flink.FlinkPipelineOptions;
import org.apache.beam.sdk.Pipeline;
import org.apache.beam.sdk.options.Default;
import org.apache.beam.sdk.options.Description;
import org.apache.beam.sdk.options.PipelineOptionsFactory;
import org.apache.beam.sdk.options.StreamingOptions;
import org.apache.beam.sdk.transforms.MapElements;
import org.apache.beam.sdk.transforms.ParDo;
import org.apache.beam.sdk.transforms.DoFn;
import org.apache.beam.sdk.values.KV;
import org.apache.beam.sdk.values.PCollection;
import org.apache.beam.sdk.values.TypeDescriptors;

public final class App {
    private static final FluentLogger logger = FluentLogger.forEnclosingClass();

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
    App(CreateCandles createCandles,
        KafkaReadTransform<String, byte[]> kafkaReadTransform,
        ParseTrades parseTrades) {
        this.createCandles = createCandles;
        this.kafkaReadTransform = kafkaReadTransform;
        this.parseTrades = parseTrades;
        logger.atInfo().log("App initialized with CreateCandles: %s, KafkaReadTransform: %s, ParseTrades: %s",
                createCandles.getClass().getSimpleName(),
                kafkaReadTransform.getClass().getSimpleName(),
                parseTrades.getClass().getSimpleName());
    }

    private Pipeline buildPipeline(Pipeline pipeline) {
        logger.atInfo().log("Building pipeline: starting to read from Kafka");
        PCollection<byte[]> input = pipeline.apply("Read from Kafka", kafkaReadTransform);

        logger.atInfo().log("Applying ParseTrades transform");
        input.apply("Parse Trades", parseTrades);

        // Optionally, you can add more logging for additional transforms if needed.
        logger.atInfo().log("Pipeline building complete");
        return pipeline;
    }

    private void runPipeline(Pipeline pipeline) {
        logger.atInfo().log("Running pipeline");
        buildPipeline(pipeline);
        try {
            pipeline.run();
            logger.atInfo().log("Pipeline successfully submitted");
        } catch (Exception e) {
            logger.atSevere().withCause(e).log("Pipeline execution failed");
            throw e;
        }
    }

    public static void main(String[] args) {
        logger.atInfo().log("Starting application with arguments: %s", (Object) args);

        // Parse custom options
        var options = PipelineOptionsFactory.fromArgs(args)
            .withValidation()
            .as(Options.class);
        logger.atInfo().log("Parsed pipeline options: BootstrapServers=%s, TradeTopic=%s, RunMode=%s",
                options.getBootstrapServers(), options.getTradeTopic(), options.getRunMode());

        // Convert to FlinkPipelineOptions and set required properties
        FlinkPipelineOptions flinkOptions = options.as(FlinkPipelineOptions.class);
        flinkOptions.setAttachedMode(false);
        flinkOptions.setStreaming(true);
        logger.atInfo().log("Configured FlinkPipelineOptions: AttachedMode=%s, Streaming=%s",
                flinkOptions.getAttachedMode(), flinkOptions.isStreaming());

        var module = PipelineModule.create(
            options.getBootstrapServers(),
            options.getTradeTopic(),
            options.getRunMode());
        logger.atInfo().log("Created Guice module with parameters");

        var injector = Guice.createInjector(module);
        var app = injector.getInstance(App.class);
        logger.atInfo().log("Retrieved App instance from Guice injector");

        var pipeline = Pipeline.create(options);
        logger.atInfo().log("Created Beam pipeline");
        app.runPipeline(pipeline);
    }
}
