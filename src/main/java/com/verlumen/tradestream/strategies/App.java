package com.verlumen.tradestream.strategies;

import com.google.common.flogger.FluentLogger;
import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.Provider;
import com.verlumen.tradestream.execution.ExecutionModule;
import com.verlumen.tradestream.execution.RunMode;
import com.verlumen.tradestream.kafka.KafkaModule;
import com.verlumen.tradestream.kafka.KafkaProperties;
import net.sourceforge.argparse4j.ArgumentParsers;
import net.sourceforge.argparse4j.inf.ArgumentParser;
import net.sourceforge.argparse4j.inf.ArgumentParserException;
import net.sourceforge.argparse4j.inf.Namespace;

/**
 * Main entry point for the Strategy Module. Coordinates data flow between components and manages the
 * lifecycle of the strategy system.
 */
final class App {
  private static final FluentLogger logger = FluentLogger.forEnclosingClass();

  private volatile boolean isRunning = false;
  private final MarketDataConsumer marketDataConsumer;
  private final RunMode runMode;
  private final Provider<StrategyEngine> strategyEngine;

  @Inject
  App(
      MarketDataConsumer marketDataConsumer,
      RunMode runMode,
      Provider<StrategyEngine> strategyEngine) {
    this.marketDataConsumer = marketDataConsumer;
    this.runMode = runMode;
    this.strategyEngine = strategyEngine;
  }

  /** Starts all strategy module components */
  public void start() {
    logger.atInfo().log("Starting real-time strategy discovery...");
    if (RunMode.DRY.equals(runMode)) {
      try {
        logger.atInfo().log("Sleeping for one minute before exiting dry run");
        Thread.sleep(60_000L); // Sleep for 60,000 milliseconds (1 minute)
      } catch (InterruptedException e) {
        logger.atWarning().withCause(e).log("Sleep interrupted during dry run");
        Thread.currentThread().interrupt(); // Restore the interrupted status
      }
      return;
    }

    try {
      isRunning = true;
      marketDataConsumer.startConsuming(strategyEngine::handleCandle);
      logger.atInfo().log("Strategy Engine service started successfully");
    } catch (Exception e) {
      logger.atSevere().withCause(e).log("Failed to start Strategy Engine service");
      throw new RuntimeException("Service start failed", e);
    }
  }

  /** Gracefully shuts down the strategy engine and stops consuming market data. */
  public void shutdown() {
    logger.atInfo().log("Shutting down Strategy Engine service...");
    try {
      isRunning = false;
      marketDataConsumer.stopConsuming();
      logger.atInfo().log("Strategy Engine service stopped successfully");
    } catch (Exception e) {
      logger.atSevere().withCause(e).log("Error during Strategy Engine service shutdown");
      // Still throw since we're shutting down anyway
      throw new RuntimeException("Service shutdown failed", e);
    }
  }

  public static void main(String[] args) {
    logger.atInfo().log("Initializing Strategy Engine service...");

    ArgumentParser argumentParser = createArgumentParser();
    Namespace namespace = argumentParser.parseArgs(args);
    KafkaProperties kafkaProperties = new KafkaProperties(
      namespace.get("kafka.acks"),
      namespace.getInt("kafka.batch.size"),
      namespace.getString("kafka.bootstrap.servers"),
      namespace.getInt("kafka.retries"),
      namespace.getInt("kafka.linger.ms"),
      namespace.getInt("kafka.buffer.memory"),
      namespace.getString("kafka.key.serializer"),
      namespace.getString("kafka.value.serializer"),
      namespace.getString("kafka.security.protocol"),
      namespace.getString("kafka.sasl.mechanism"),
      namespace.getString("kafka.sasl.jaas.config"));
    String candleTopic = namespace.getString("candleTopic");
    String signalTopic = namespace.getString("tradeSignalTopic");
    String runModeName = namespace.getString("runMode");
    App app =
        Guice.createInjector(
          ExecutionModule.create(runModeName),
          KafkaModule.create(kafkaProperties),
          StrategiesModule.create(candleTopic, signalTopic))
      .getInstance(App.class);

    // Add shutdown hook for graceful termination
    Runtime.getRuntime()
        .addShutdownHook(
            new Thread(
                () -> {
                  logger.atInfo().log("Shutdown hook triggered");
                  app.shutdown();
                }));
    // Start the service
    app.start();
  }

  private static ArgumentParser createArgumentParser() {
    ArgumentParser parser =
        ArgumentParsers.newFor("TradestreamStrategyEngine")
            .build()
            .defaultHelp(true)
            .description("Configuration for Kafka producer and exchange settings");

    parser.addArgument("--candleTopic")
      .type(String.class)
      .setDefault("candles")
      .help("Kafka topic to subscribe to candle data");

    // Kafka configuration
    parser.addArgument("--kafka.bootstrap.servers")
      .setDefault("localhost:9092")
      .help("Kafka bootstrap servers");

    parser.addArgument("--kafka.acks")
      .setDefault("all")
      .help("Kafka acknowledgment configuration");

    parser.addArgument("--kafka.retries")
      .type(Integer.class)
      .setDefault(0)
      .help("Number of retries");

    parser.addArgument("--kafka.batch.size")
      .type(Integer.class)
      .setDefault(16384)
      .help("Batch size in bytes");

    parser.addArgument("--kafka.linger.ms")
      .type(Integer.class)
      .setDefault(1)
      .help("Linger time in milliseconds");

    parser.addArgument("--kafka.buffer.memory")
      .type(Integer.class)
      .setDefault(33554432)
      .help("Buffer memory in bytes");

    parser.addArgument("--kafka.key.serializer")
      .setDefault("org.apache.kafka.common.serialization.StringSerializer")
      .help("Key serializer class");

    parser.addArgument("--kafka.value.serializer")
      .setDefault("org.apache.kafka.common.serialization.ByteArraySerializer")
      .help("Value serializer class");

    // SASL configuration
    parser.addArgument("--kafka.security.protocol")
      .setDefault("PLAINTEXT")
      .help("Protocol used to communicate with brokers (e.g., PLAINTEXT, SASL_SSL)");

    parser.addArgument("--kafka.sasl.mechanism")
      .setDefault("")
      .help("SASL mechanism used for authentication (e.g., PLAIN, SCRAM-SHA-256)");

    parser.addArgument("--kafka.sasl.jaas.config")
      .setDefault("")
      .help("SASL JAAS configuration");

    // Run mode configuration
    parser.addArgument("--runMode").choices("wet", "dry").help("Run mode: wet or dry");

    parser.addArgument("--tradeSignalTopic")
      .type(String.class)
      .setDefault("tradeSignals")
      .help("Kafka topic to publish signal data");

    return parser;
  }
}
