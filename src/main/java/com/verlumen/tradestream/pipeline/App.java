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
import com.verlumen.tradestream.marketdata.CandleLookbackDoFn;
import com.verlumen.tradestream.marketdata.CandleSource;
import com.verlumen.tradestream.strategies.StrategyEnginePipeline;
import java.util.List;
import java.util.Arrays;
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
  private static final String TIINGO_API_KEY_ENV_VAR = "TIINGO_API_KEY";

  /**
   * A constant string holding the Fibonacci sequence values less than 526,000.
   *
   * The upper limit (526,000) was chosen as it approximates the number of
   * minutes in an average Gregorian year (365.25 days).
   * Calculation: 365.25 days * 24 hours/day * 60 minutes/hour = 525,960 minutes.
   */
  private static final String FIBONACCI_UNDER_APPROX_MINUTES_IN_YEAR = "0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610, 987, 1597, 2584, 4181, 6765, 10946, 17711, 28657, 46368, 75025, 121393, 196418, 317811, 514229";
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
    
    @Description("Candle lookback sizes (comma-separated list of integers)")
    @Default.String(FIBONACCI_UNDER_APPROX_MINUTES_IN_YEAR)
    String getCandleLookbackSizes();
    void setCandleLookbackSizes(String value);

    @Description("Tiingo API Key (default: value of " + TIINGO_API_KEY_ENV_VAR + " environment variable)")
    @Default.String("")
    String getTiingoApiKey();
    void setTiingoApiKey(String value);
  }

  private final Supplier<List<CurrencyPair>> currencyPairs;
  private final StrategyEnginePipeline strategyEnginePipeline;
  private final TimingConfig timingConfig;

  @Inject
  App(
      CandleSource candleSource,
      Supplier<List<CurrencyPair>> currencyPairs,
      StrategyEnginePipeline strategyEnginePipeline,
      TimingConfig timingConfig) {
    this.currencyPairs = currencyPairs;
    this.strategyEnginePipeline = strategyEnginePipeline;
    this.timingConfig = timingConfig;
  }

  /** Build the Beam pipeline, integrating all components. */
  private Pipeline buildPipeline(Pipeline pipeline, Options options) {
    logger.atInfo().log("Starting to build the pipeline.");

    // 1. Read candles.
    PCollection<KV<String, Candle>> candles = pipeline.apply("LoadCandles", canldeSource);
      
    // 2. Apply window for candle processing - use a single large window for stateful processing
    Duration windowDuration = Duration.standardMinutes(options.getCandleDurationMinutes() * 10);
    PCollection<KV<String, Candle>> windowedCandles = candles.apply(
        "Apply Processing Window",
        Window.<KV<String, Candle>>into(FixedWindows.of(windowDuration))
            .triggering(DefaultTrigger.of())
            .discardingFiredPanes());
            
    // 3. Parse lookback sizes from options and add lookback processing
    List<Integer> lookbackSizes = parseLookbackSizes(options.getCandleLookbackSizes());
    PCollection<KV<String, KV<Integer, ImmutableList<Candle>>>> lookbacks = windowedCandles.apply(
        "Generate Candle Lookbacks",
        ParDo.of(new CandleLookbackDoFn(lookbackSizes)));
        
    // 4. Log lookback results for debugging
    lookbacks.apply("Log Lookbacks", ParDo.of(new LogLookbacksDoFn()));

    logger.atInfo().log("Pipeline building complete. Returning pipeline.");
    return pipeline;
  }

  /** Parse the comma-separated lookback sizes into a List of Integers */
  private List<Integer> parseLookbackSizes(String sizesString) {
    return Arrays.stream(sizesString.split(","))
        .map(String::trim)
        .filter(s -> !s.isEmpty())
        .map(Integer::parseInt)
        .filter(i -> i > 20_160) // TWO WEEKS
        .distinct()
        .toList();
  }
  
  /** DoFn to log lookback results */
  private static class LogLookbacksDoFn extends DoFn<KV<String, KV<Integer, ImmutableList<Candle>>>, Void> {
    private static final FluentLogger logger = FluentLogger.forEnclosingClass();
    
    @ProcessElement
    public void processElement(ProcessContext c) {
      KV<String, KV<Integer, ImmutableList<Candle>>> element = c.element();
      String currencyPair = element.getKey();
      int lookbackSize = element.getValue().getKey();
      ImmutableList<Candle> candles = element.getValue().getValue();
      
      logger.atInfo().log(
          "Generated lookback for %s: size=%d, elements=%d",
          currencyPair, lookbackSize, candles.size());
    }
  }

  private void runPipeline(Pipeline pipeline, Options options) throws Exception {
    logger.atInfo().log("Running the pipeline.");

    buildPipeline(pipeline, options);
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

  private static String getTiingoApiKey(Options options) {
      if (isNullOrEmpty(options.getTiingoApiKey())) {
           return System.getenv().getOrDefault(TIINGO_API_KEY_ENV_VAR, "INVALID_API_KEY");
      } 

      return options.getTiingoApiKey();
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
      options.getCoinMarketCapTopCurrencyCount(),
      options.getTiingoApiKey());
    logger.atInfo().log("Created Guice module.");

    // Initialize the application via Guice.
    var injector = Guice.createInjector(module);
    App app = injector.getInstance(App.class);
    logger.atInfo().log("Retrieved App instance from Guice injector.");

    // Create and run the Beam pipeline.
    Pipeline pipeline = Pipeline.create(options);
    logger.atInfo().log("Created Beam pipeline.");
    app.runPipeline(pipeline, options);
  }
}
