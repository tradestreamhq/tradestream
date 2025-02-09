package com.verlumen.tradestream.pipeline;

import static com.google.common.base.MoreObjects.firstNonNull;
import static com.google.common.collect.Iterables.getLast;

import com.google.common.flogger.FluentLogger;
import com.google.protobuf.util.Timestamps;
import com.google.inject.Guice;
import com.google.inject.Inject;
import com.verlumen.tradestream.kafka.KafkaReadTransform;
import com.verlumen.tradestream.marketdata.Candle;
import com.verlumen.tradestream.marketdata.MultiTimeframeCandleTransform;
import com.verlumen.tradestream.marketdata.CandleStreamWithDefaults;
import com.verlumen.tradestream.marketdata.ParseTrades;
import com.verlumen.tradestream.marketdata.Trade;
import java.util.Arrays;
import org.apache.beam.runners.flink.FlinkPipelineOptions;
import org.apache.beam.sdk.Pipeline;
import org.apache.beam.sdk.options.Default;
import org.apache.beam.sdk.options.Description;
import org.apache.beam.sdk.options.PipelineOptionsFactory;
import org.apache.beam.sdk.options.StreamingOptions;
import org.apache.beam.sdk.transforms.DoFn;
import org.apache.beam.sdk.transforms.DoFn.ProcessContext;
import org.apache.beam.sdk.transforms.DoFn.ProcessElement;
import org.apache.beam.sdk.transforms.MapElements;
import org.apache.beam.sdk.transforms.ParDo;
import org.apache.beam.sdk.transforms.WithTimestamps;
import org.apache.beam.sdk.transforms.windowing.DefaultTrigger;
import org.apache.beam.sdk.transforms.windowing.FixedWindows;
import org.apache.beam.sdk.transforms.windowing.Window;
import org.apache.beam.sdk.values.KV;
import org.apache.beam.sdk.values.PCollection;
import org.apache.beam.sdk.values.TypeDescriptor;
import org.joda.time.Duration;
import org.joda.time.Instant;
import com.google.common.collect.ImmutableList;

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
  private final Duration windowDuration;
  private final KafkaReadTransform<String, byte[]> kafkaReadTransform;
  private final ParseTrades parseTrades;

  @Inject
  App(
      KafkaReadTransform<String, byte[]> kafkaReadTransform,
      ParseTrades parseTrades,
      PipelineConfig config) {
    this.allowedLateness = config.allowedLateness();
    this.allowedTimestampSkew = config.allowedTimestampSkew();
    this.windowDuration = config.windowDuration(); // e.g. 1 minute windows for candles.
    this.kafkaReadTransform = kafkaReadTransform;
    this.parseTrades = parseTrades;
    logger.atInfo().log(
        "Initialized App with allowedLateness=%s, windowDuration=%s, allowedTimestampSkew=%s",
        allowedLateness, windowDuration, allowedTimestampSkew);
  }

  /**
   * Build the Beam pipeline, integrating all components.
   */
  private Pipeline buildPipeline(Pipeline pipeline) {
    logger.atInfo().log("Starting to build the pipeline.");

    // 1. Read from Kafka.
    PCollection<byte[]> input = pipeline.apply("ReadFromKafka", kafkaReadTransform);

    // 2. Parse the byte stream into Trade objects.
    PCollection<Trade> trades = input.apply("ParseTrades", parseTrades);

    // 3. Assign event timestamps from the Trade's own timestamp.
    PCollection<Trade> tradesWithTimestamps =
        trades.apply(
            "AssignTimestamps",
            WithTimestamps.of((Trade trade) -> {
              long millis = Timestamps.toMillis(trade.getTimestamp());
              Instant timestamp = new Instant(millis);
              logger.atFinest().log("Assigned timestamp %s for trade: %s", timestamp, trade);
              return timestamp;
            }).withAllowedTimestampSkew(allowedTimestampSkew)
        );

    // 4. Convert trades into KV pairs keyed by currency pair.
    PCollection<KV<String, Trade>> tradePairs =
        tradesWithTimestamps.apply(
            "CreateTradePairs",
            MapElements.into(new TypeDescriptor<KV<String, Trade>>() {})
                .via((Trade trade) -> {
                  String key = trade.getCurrencyPair();  // Expect currency pair as String.
                  logger.atFinest().log("Mapping trade %s to key: %s", trade, key);
                  return KV.of(key, trade);
                })
        );

    // 5. Apply fixed windowing (1 minute windows).
    PCollection<KV<String, Trade>> windowedTradePairs =
        tradePairs.apply(
            "ApplyWindows",
            Window.<KV<String, Trade>>into(FixedWindows.of(windowDuration))
                .withAllowedLateness(allowedLateness)
                .triggering(DefaultTrigger.of())
                .discardingFiredPanes()
        );

    // 6. Create a base candle stream from the windowed trades.
    // This transform unites real trades with synthetic default trades,
    // aggregates them into 1-minute candles (using SlidingCandleAggregator), and buffers the last N candles.
    PCollection<KV<String, ImmutableList<Candle>>> baseCandleStream =
        windowedTradePairs.apply(
            "CreateBaseCandles",
            new CandleStreamWithDefaults(
                windowDuration,                  // Use the same 1-minute window for candle aggregation.
                Duration.standardSeconds(30),    // Slide duration for the candle aggregator.
                5,                               // Buffer size for base candle consolidation.
                Arrays.asList("BTC/USD", "ETH/USD"),
                10000.0                          // Default price for synthetic trades.
            )
        );

    // 7. Convert the buffered list into a single consolidated candle per key.
    // For example, take the last element of the buffered list.
    PCollection<KV<String, Candle>> consolidatedBaseCandles =
        baseCandleStream.apply("ConsolidateBufferedCandles",
            MapElements.into(new TypeDescriptor<KV<String, Candle>>() {})
                .via((KV<String, ImmutableList<Candle>> kv) -> {
                  ImmutableList<Candle> list = firstNonNull(kv.getValue(), ImmutableList.of());
                  Candle consolidated = getLast(list, Candle.getDefaultInstance());
                  return KV.of(kv.getKey(), consolidated);
                })
        );

    // 8. Apply the multi-timeframe view.
    // This transform branches the base candle stream into different timeframes,
    // for example, a 1-hour view (last 60 candles) and a 1-day view (last 1440 candles).
    PCollection<KV<String, ImmutableList<Candle>>> multiTimeframeStream =
        consolidatedBaseCandles.apply("MultiTimeframeView", new MultiTimeframeCandleTransform());

    // 9. Print the results to stdout with helpful labels.
    multiTimeframeStream.apply("PrintResults", ParDo.of(new PrintResultsDoFn()));

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

  private static class PrintResultsDoFn extends DoFn<KV<String, ImmutableList<Candle>>, Void> {
    @ProcessElement
    public void processElement(ProcessContext c) {
      KV<String, ImmutableList<Candle>> element = c.element();
      System.out.println("Currency Pair: " + element.getKey() + " | Timeframe View: " + element.getValue());
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
