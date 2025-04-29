package com.verlumen.tradestream.pipeline;

import static com.google.common.base.MoreObjects.firstNonNull;
import static com.google.common.base.Strings.isNullOrEmpty;
import static com.google.common.collect.Iterables.getLast;

import com.google.common.base.Suppliers;
import com.google.common.collect.ImmutableList;
import com.google.common.flogger.FluentLogger;
import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.protobuf.util.Timestamps;
import com.verlumen.tradestream.execution.RunMode;
import com.verlumen.tradestream.instruments.CurrencyPair;
import com.verlumen.tradestream.marketdata.Candle;
import com.verlumen.tradestream.marketdata.FillForwardCandles;
import com.verlumen.tradestream.marketdata.MultiTimeframeCandleTransform;
import com.verlumen.tradestream.marketdata.Trade;
import com.verlumen.tradestream.marketdata.TradeSource;
import com.verlumen.tradestream.marketdata.TradeToCandle;
import com.verlumen.tradestream.strategies.StrategyEnginePipeline;
import java.util.List;
import java.util.function.Supplier;
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

public final class App {
  private static final FluentLogger logger = FluentLogger.forEnclosingClass();

  private static final String CMC_API_KEY_ENV_VAR = "COINMARKETCAP_API_KEY";
  private static final Duration ONE_MINUTE = Duration.standardMinutes(1);

  public interface Options extends StreamingOptions {
    @Description("Comma-separated list of Kafka bootstrap servers.")
    @Default.String("localhost:9092")
    String getBootstrapServers();
    void setBootstrapServers(String value);

    @Description("Duration of candles in minutes.")
    @Default.Integer(1)
    int getCandleDurationMinutes();
    void setCandleDurationMinutes(int value);

    @Description("Name of the exchange.")
    @Default.String("coinbase")
    String getExchangeName();
    void setExchangeName(String value);

    @Description("Maximum number of forward intervals to fill for missing candles.")
    @Default.Integer(Integer.MAX_VALUE)
    int getMaxForwardIntervals();
    void setMaxForwardIntervals(int value);

    @Description("Kafka topic to publish signal data to.")
    @Default.String("signals")
    String getSignalTopic();
    void setSignalTopic(String value);

    @Description("Run mode: wet or dry.")
    @Default.String("wet")
    String getRunMode();
    void setRunMode(String value);

    @Description("CoinMarketCap API Key (default: value of " + CMC_API_KEY_ENV_VAR + " environment variable)")
    @Default.String("")
    String getCoinMarketCapApiKey();
    void setCoinMarketCapApiKey(String value);

    @Description("Number of top cryptocurrencies to track (default: 10)")
    @Default.Integer(10)
    int getCoinMarketCapTopCurrencyCount();
    void setCoinMarketCapTopCurrencyCount(int value);
  }

  private final Supplier<List<CurrencyPair>> currencyPairs;
  private final FillForwardCandles fillForwardCandles;
  private final StrategyEnginePipeline strategyEnginePipeline;
  private final TimingConfig timingConfig;
  private final TradeSource tradeSource;
  private final TradeToCandle tradeToCandle;

  @Inject
  App(
      Supplier<List<CurrencyPair>> currencyPairs,
      FillForwardCandles fillForwardCandles,
      StrategyEnginePipeline strategyEnginePipeline,
      TimingConfig timingConfig,
      TradeSource tradeSource,
      TradeToCandle tradeToCandle) {
    this.currencyPairs = currencyPairs;
    this.fillForwardCandles = fillForwardCandles;
    this.strategyEnginePipeline = strategyEnginePipeline;
    this.timingConfig = timingConfig;
    this.tradeSource = tradeSource;
    this.tradeToCandle = tradeToCandle;
  }

  /** Build the Beam pipeline, integrating all components. */
  private Pipeline buildPipeline(Pipeline pipeline) {
    logger.atInfo().log("Starting to build the pipeline.");

    // 1. Read trades.
    PCollection<Trade> trades = pipeline.apply("ReadTrades", tradeSource);

    // 2. Assign event timestamps from the Trade's own timestamp.
    PCollection<Trade> tradesWithTimestamps =
        trades.apply(
            "AssignTimestamps",
            WithTimestamps.<Trade>of(
                    trade -> {
                      long millis = Timestamps.toMillis(trade.getTimestamp());
                      Instant timestamp = new Instant(millis);
                      logger.atInfo().log("Assigned timestamp %s for trade: %s", timestamp, trade);
                      return timestamp;
                    })
                .withAllowedTimestampSkew(timingConfig.allowedTimestampSkew()));

    // 3. Create candles from trades.
    PCollection<KV<String, Candle>> candles = tradesWithTimestamps
      .apply("Create Candle", tradeToCandle);

    logger.atInfo().log("Pipeline building complete. Returning pipeline.");
    return pipeline;
  }

  private void runPipeline(Pipeline pipeline) throws Exception {
    logger.atInfo().log("Running the pipeline.");

    buildPipeline(pipeline);
    pipeline.run();
  }

  private static class PrintResultsDoFn extends DoFn<KV<String, ImmutableList<Candle>>, Void> {
    @ProcessElement
    public void processElement(ProcessContext c) {
      KV<String, ImmutableList<Candle>> element = c.element();
      System.out.println(
          "Currency Pair: " + element.getKey() + " | Timeframe View: " + element.getValue());
    }
  }

  private static String getCmcApiKey(Options options) {
      if (isNullOrEmpty(options.getCoinMarketCapApiKey())) {
           return System.getenv().getOrDefault(CMC_API_KEY_ENV_VAR, "INVALID_API_KEY");
      } 

      return options.getCoinMarketCapApiKey();
  }

  public static void main(String[] args) throws Exception {
    logger.atInfo().log("Application starting with arguments: %s", (Object) args);

    // Parse custom options.
    Options options = PipelineOptionsFactory.fromArgs(args).withValidation().as(Options.class);
    logger.atInfo()
        .log(
            "Parsed options: BootstrapServers=%s, RunMode=%s",
            options.getBootstrapServers(), options.getRunMode());

    // Convert to FlinkPipelineOptions and set required properties.
    FlinkPipelineOptions flinkOptions = options.as(FlinkPipelineOptions.class);
    flinkOptions.setAttachedMode(false);
    flinkOptions.setStreaming(true);
    logger.atInfo()
        .log(
            "Configured FlinkPipelineOptions: AttachedMode=%s, Streaming=%s",
            flinkOptions.getAttachedMode(), flinkOptions.isStreaming());

    // Create Guice module.
    RunMode runMode = RunMode.fromString(options.getRunMode());
    var module = PipelineModule.create(
      options.getBootstrapServers(),
      options.getCandleDurationMinutes(),
      getCmcApiKey(options),
      options.getExchangeName(),
      options.getMaxForwardIntervals(),
      runMode,
      options.getSignalTopic(),
      options.getCoinMarketCapTopCurrencyCount());
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
