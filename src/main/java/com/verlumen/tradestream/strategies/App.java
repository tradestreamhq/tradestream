package com.verlumen.tradestream.strategies;

import com.google.common.flogger.FluentLogger;
import com.google.inject.Guice;
import com.google.inject.Inject;
import com.verlumen.tradestream.execution.ExecutionModule;
import com.verlumen.tradestream.execution.RunMode;
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

  private final MarketDataConsumer marketDataConsumer;
  private final RunMode runMode;
  private final StrategyEngine strategyEngine;

  @Inject
  App(MarketDataConsumer marketDataConsumer, RunMode runMode, StrategyEngine strategyEngine) {
    this.marketDataConsumer = marketDataConsumer;
    this.runMode = runMode;
    this.strategyEngine = strategyEngine;
  }

  /** Starts all strategy module components */
  public void start() {
    logger.atInfo().log("Starting real-time strategy discovery...");
    if (RunMode.DRY.equals(runMode)) {
      return;
    }
  }

  /** Gracefully shuts down all strategy module components */
  public void shutdown() {}

  interface Factory {
    App create(RunMode runMode);
  }

  public static void main(String[] args) throws ArgumentParserException {
    logger.atInfo().log("TradeStream application starting up with %d arguments", args.length);

    ArgumentParser argumentParser = createArgumentParser();
    Namespace namespace = argumentParser.parseArgs(args);
    String runModeName = namespace.getString("runMode");
    App app =
        Guice.createInjector(ExecutionModule.create(runModeName), StrategiesModule.create())
            .getInstance(App.class);

    // Start the service
    app.start();
  }

  private static ArgumentParser createArgumentParser() {
    ArgumentParser parser =
        ArgumentParsers.newFor("TradestreamStrategyEngine")
            .build()
            .defaultHelp(true)
            .description("Configuration for Kafka producer and exchange settings");

    // Run mode configuration
    parser.addArgument("--runMode").choices("wet", "dry").help("Run mode: wet or dry");

    return parser;
  }
}
