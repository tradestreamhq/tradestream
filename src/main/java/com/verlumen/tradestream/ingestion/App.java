package com.verlumen.tradestream.ingestion;

import com.google.common.flogger.FluentLogger;
import com.google.inject.Guice;
import com.google.inject.Inject;
import com.verlumen.tradestream.execution.RunMode;
import com.verlumen.tradestream.kafka.KafkaProperties;
import net.sourceforge.argparse4j.ArgumentParsers;
import net.sourceforge.argparse4j.inf.ArgumentParser;
import net.sourceforge.argparse4j.inf.Namespace;

final class App {
  private static final FluentLogger logger = FluentLogger.forEnclosingClass();
  private static final String API_KEY_ENV_VAR = "COINMARKETCAP_API_KEY";

  private final RealTimeDataIngestion realTimeDataIngestion;
  private final RunMode runMode;

  @Inject
  App(RealTimeDataIngestion realTimeDataIngestion, RunMode runMode) {
    logger.atInfo().log("Creating App instance with runMode: %s", runMode);
    this.realTimeDataIngestion = realTimeDataIngestion;
    this.runMode = runMode;
  }

  void run() {
    logger.atInfo().log("Starting real-time data ingestion...");
    logger.atInfo().log("Starting application in %s mode", runMode);
    if (runMode == RunMode.DRY) {
      logger.atInfo().log("Dry run mode detected - skipping data ingestion");
      return;
    }

    try {
      logger.atInfo().log("Initiating real-time data ingestion...");
      realTimeDataIngestion.start();
      logger.atInfo().log("Real-time data ingestion started successfully");
    } catch (Exception e) {
      logger.atSevere().withCause(e).log("Failed to start real-time data ingestion");
      throw e;
    }
  }

  public static void main(String[] args) throws Exception {
    logger.atInfo().log("TradeStream application starting up with %d arguments", args.length);
    try {
      logger.atInfo().log("Initializing Guice injector with IngestionModule");
      Namespace namespace = createParser().parseArgs(args);
      String candlePublisherTopic = namespace.getString("candlePublisherTopic");
      String coinMarketCapApiKey = namespace.getString("coinmarketcap.apiKey");
      int topNCryptocurrencies = namespace.getInt("coinmarketcap.topN");
      String exchangeName = namespace.getString("exchangeName");
      long candleIntervalMillis = namespace.getInt("candleIntervalSeconds") * 1000L;
      String runModeName = namespace.getString("runMode").toUpperCase();
      RunMode runMode = RunMode.valueOf(runModeName);
      KafkaProperties kafkaProperties =
          KafkaProperties.createFromKafkaPrefixedProperties(namespace.getAttrs());
      IngestionConfig ingestionConfig =
          new IngestionConfig(
              candlePublisherTopic,
              coinMarketCapApiKey,
              topNCryptocurrencies,
              exchangeName,
              candleIntervalMillis,
              runMode,
              kafkaProperties);
      IngestionModule module = IngestionModule.create(ingestionConfig);
      App app = Guice.createInjector(module).getInstance(App.class);
      logger.atInfo().log("Guice initialization complete, running application");
      app.run();
    } catch (Exception e) {
      logger.atSevere().withCause(e).log("Fatal error during application startup");
      throw e;
    }
  }

  private static ArgumentParser createParser() {
    ArgumentParser parser = ArgumentParsers.newFor("TradeStreamDataIngestion")
      .build()
      .defaultHelp(true)
      .description("Configuration for Kafka producer and exchange settings");

    // Existing arguments
    parser.addArgument("--candleIntervalSeconds")
      .type(Integer.class)
      .setDefault(60)
      .help("Candle interval in seconds");

    parser.addArgument("--candlePublisherTopic")
      .setDefault("candles")
      .help("Kafka topic to publish candle data");

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

    // Exchange configuration
    parser.addArgument("--exchangeName")
      .setDefault("coinbase")
      .help("Exchange name");

    // CoinMarketCap configuration
    parser.addArgument("--coinmarketcap.apiKey")
      .setDefault(System.getenv().getOrDefault(API_KEY_ENV_VAR, "INVALID_API_KEY"))
      .help("CoinMarketCap API Key (default: value of " + API_KEY_ENV_VAR + " environment variable)");

    parser.addArgument("--coinmarketcap.topN")
      .type(Integer.class)
      .setDefault(10)
      .help("Number of top cryptocurrencies to track (default: 100)");

    // Run mode configuration
    parser.addArgument("--runMode")
      .choices("wet", "dry")
      .help("Run mode: wet or dry");

    return parser;
  }
}
