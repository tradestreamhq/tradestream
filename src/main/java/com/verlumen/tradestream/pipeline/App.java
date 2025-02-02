package com.verlumen.tradestream.pipeline;

import com.google.common.flogger.FluentLogger;
import com.google.protobuf.util.Timestamps;
import com.google.inject.Guice;
import com.google.inject.Inject;
import com.verlumen.tradestream.kafka.KafkaReadTransform;
import com.verlumen.tradestream.marketdata.Candle;
import com.verlumen.tradestream.marketdata.CreateCandles;
import com.verlumen.tradestream.marketdata.ParseTrades;
import com.verlumen.tradestream.marketdata.Trade;
import org.apache.beam.runners.flink.FlinkPipelineOptions;
import org.apache.beam.sdk.Pipeline;
import org.apache.beam.sdk.options.Default;
import org.apache.beam.sdk.options.Description;
import org.apache.beam.sdk.options.PipelineOptionsFactory;
import org.apache.beam.sdk.options.StreamingOptions;
import org.apache.beam.sdk.transforms.MapElements;
import org.apache.beam.sdk.transforms.WithTimestamps;
import org.apache.beam.sdk.transforms.windowing.DefaultTrigger;
import org.apache.beam.sdk.transforms.windowing.FixedWindows;
import org.apache.beam.sdk.transforms.windowing.Window;
import org.apache.beam.sdk.values.KV;
import org.apache.beam.sdk.values.PCollection;
import org.apache.beam.sdk.values.TypeDescriptor;
import org.joda.time.Duration;
import org.joda.time.Instant;

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

  private final Duration allowedLateness;
  private final Duration allowedTimestampSkew;
  private final CreateCandles createCandles;
  private final KafkaReadTransform<String, byte[]> kafkaReadTransform;
  private final ParseTrades parseTrades;
  private final Duration windowDuration;

  @Inject
  App(
      CreateCandles createCandles,
      KafkaReadTransform<String, byte[]> kafkaReadTransform,
      ParseTrades parseTrades,
      PipelineConfig config) {
    this.allowedLateness = config.allowedLateness();
    this.allowedTimestampSkew = config.allowedTimestampSkew();
    this.createCandles = createCandles;
    this.kafkaReadTransform = kafkaReadTransform;
    this.parseTrades = parseTrades;
    this.windowDuration = config.windowDuration();
    logger.atInfo().log(
        "Initialized App with allowedLateness=%s, windowDuration=%s, allowedTimestampSkew=%s",
        allowedLateness,
        windowDuration,
        allowedTimestampSkew);
  }

  private Pipeline buildPipeline(Pipeline pipeline) {
    logger.atInfo().log("Starting to build the pipeline.");

    // 1. Read from Kafka (returns PCollection<byte[]>)
    logger.atInfo().log("Applying KafkaReadTransform to read from Kafka.");
    PCollection<byte[]> input = pipeline.apply("Read from Kafka", kafkaReadTransform);

    // 2. Parse bytes into Trade objects.
    logger.atInfo().log("Applying ParseTrades transform.");
    PCollection<Trade> trades = input.apply("Parse Trades", parseTrades);

    // 3. Assign proper event timestamps (using the Trade's own timestamp).
    logger.atInfo().log("Assigning event timestamps based on Trade timestamps with skew=%s", allowedTimestampSkew);
    PCollection<Trade> tradesWithTimestamps =
        trades.apply(
            "Assign Timestamps",
            WithTimestamps.of(
                (Trade trade) -> {
                    long millis = Timestamps.toMillis(trade.getTimestamp());
                    Instant timestamp = new Instant(millis);
                    logger.atFinest().log("Assigned timestamp %s for trade: %s", timestamp, trade);
                    return timestamp;
                })
            .withAllowedTimestampSkew(allowedTimestampSkew));

    // 4. Convert to KV pairs (keyed by currency pair).
    logger.atInfo().log("Mapping trades to KV pairs keyed by currency pair.");
    PCollection<KV<String, Trade>> tradePairs =
        tradesWithTimestamps.apply(
            "Create Trade Pairs",
            MapElements.into(new TypeDescriptor<KV<String, Trade>>() {})
                .via(
                    (Trade trade) -> {
                      String key = trade.getCurrencyPair();
                      logger.atFinest().log("Mapping trade %s to key: %s", trade, key);
                      return KV.of(key, trade);
                    }));

    // 5. Apply windowing.
    logger.atInfo().log("Applying fixed windowing of duration %s with allowed lateness %s.", windowDuration,
        allowedLateness);
    PCollection<KV<String, Trade>> windowedInput =
        tradePairs.apply(
            "Apply Windows",
            Window.<KV<String, Trade>>into(FixedWindows.of(windowDuration))
                .withAllowedLateness(allowedLateness)
                .triggering(DefaultTrigger.of())
                .discardingFiredPanes());

    // 6. Create candles from windowed trades.
    logger.atInfo().log("Creating candles from windowed trade data.");
    PCollection<Candle> candles = windowedInput.apply("Create Candles", createCandles);

    logger.atInfo().log("Pipeline building complete. Returning pipeline.");
    return pipeline;
  }

  private void runPipeline(Pipeline pipeline) {
    logger.atInfo().log("Running the pipeline.");
    buildPipeline(pipeline);
    try {
      pipeline.run();
      logger.atInfo().log("Pipeline submitted successfully.");
    } catch (Exception e) {
      logger.atSevere().withCause(e).log("Pipeline execution failed.");
      throw e;
    }
  }

  public static void main(String[] args) {
    logger.atInfo().log("Application starting with arguments: %s", (Object) args);

    // Parse custom options.
    Options options =
        PipelineOptionsFactory.fromArgs(args).withValidation().as(Options.class);
    logger.atInfo().log("Parsed options: BootstrapServers=%s, TradeTopic=%s, RunMode=%s",
        options.getBootstrapServers(), options.getTradeTopic(), options.getRunMode());

    // Convert to FlinkPipelineOptions and set required properties.
    FlinkPipelineOptions flinkOptions = options.as(FlinkPipelineOptions.class);
    flinkOptions.setAttachedMode(false);
    flinkOptions.setStreaming(true);
    logger.atInfo().log("Configured FlinkPipelineOptions: AttachedMode=%s, Streaming=%s",
        flinkOptions.getAttachedMode(), flinkOptions.isStreaming());

    // Create PipelineConfig and Guice module.
    PipelineConfig config =
        PipelineConfig.create(options.getBootstrapServers(), options.getTradeTopic(), options.getRunMode());
    logger.atInfo().log("Created PipelineConfig: %s", config);

    var module = PipelineModule.create(config);
    logger.atInfo().log("Created Guice module.");

    // Initialize the application via Guice.
    var injector = Guice.createInjector(module);
    App app = injector.getInstance(App.class);
    logger.atInfo().log("Retrieved App instance from Guice injector.");

    // Create and run the Beam pipeline.
    Pipeline pipeline = Pipeline.create(options);
    logger.atInfo().log("Created Beam pipeline.");
    app.runPipeline(pipeline);
  }
}
