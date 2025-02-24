package com.verlumen.tradestream.ingestion;

import com.google.common.flogger.FluentLogger;
import com.google.inject.Guice;
import com.google.inject.Inject;
import com.verlumen.tradestream.execution.RunMode;
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
      String coinMarketCapApiKey = namespace.getString("coinmarketcap.apiKey");
      int topNCryptocurrencies = namespace.getInt("coinmarketcap.topN");
      String exchangeName = namespace.getString("exchangeName");
      String runModeName = namespace.getString("runMode").toUpperCase();
      RunMode runMode = RunMode.valueOf(runModeName);
      IngestionConfig ingestionConfig =
          new IngestionConfig(
              coinMarketCapApiKey,
              topNCryptocurrencies,
              exchangeName,
              runMode,
              namespace.getString("kafka.bootstrap.servers"),
              namespace.getString("tradeTopic"));
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

    // Kafka configuration
    parser.addArgument("--kafka.bootstrap.servers")
      .setDefault("localhost:9092")
      .help("Kafka bootstrap servers");

    // Run mode configuration
    parser.addArgument("--runMode")
      .choices("wet", "dry")
      .help("Run mode: wet or dry");

    parser.addArgument("--tradeTopic")
      .setDefault("trades")
      .help("Kafka topic for publishing trades");

    return parser;
  }
}
