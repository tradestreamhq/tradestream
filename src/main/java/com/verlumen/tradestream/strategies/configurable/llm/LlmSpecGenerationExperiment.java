package com.verlumen.tradestream.strategies.configurable.llm;

import com.verlumen.tradestream.strategies.configurable.StrategyConfig;
import java.io.IOException;
import java.nio.file.Path;
import java.util.List;
import java.util.logging.Logger;
import org.ta4j.core.BarSeries;

/**
 * Main entry point for the Phase 2 LLM Spec Generation Experiment. Generates novel strategy specs
 * using an LLM, validates them, backtests each, and reports GO/NO-GO results.
 *
 * <p>Usage: java LlmSpecGenerationExperiment [strategiesDir] [outputDir] [numSpecs]
 */
public final class LlmSpecGenerationExperiment {
  private static final Logger logger =
      Logger.getLogger(LlmSpecGenerationExperiment.class.getName());

  private static final int DEFAULT_NUM_SPECS = 10;
  private static final int DEFAULT_BAR_COUNT = 500;
  private static final int FEW_SHOT_COUNT = 7;
  private static final double TEMPERATURE = 0.8;

  public static void main(String[] args) {
    String strategiesDir = args.length > 0 ? args[0] : "src/main/resources/strategies";
    String outputDir = args.length > 1 ? args[1] : "experiments/llm_validation/results";
    int numSpecs = args.length > 2 ? Integer.parseInt(args[2]) : DEFAULT_NUM_SPECS;

    try {
      runExperiment(strategiesDir, outputDir, numSpecs);
    } catch (Exception e) {
      logger.severe("Experiment failed: " + e.getMessage());
      e.printStackTrace();
      System.exit(1);
    }
  }

  public static ExperimentRunner.ExperimentResults runExperiment(
      String strategiesDir, String outputDir, int numSpecs) throws IOException {
    // Load existing strategies
    List<StrategyConfig> allStrategies = ExperimentRunner.loadAllStrategies(strategiesDir);
    logger.info("Loaded " + allStrategies.size() + " existing strategies from " + strategiesDir);

    // Select few-shot examples
    List<StrategyConfig> fewShot =
        ExperimentRunner.selectDiverseExamples(allStrategies, FEW_SHOT_COUNT);
    logger.info("Selected " + fewShot.size() + " few-shot examples:");
    for (StrategyConfig fs : fewShot) {
      logger.info("  - " + fs.getName());
    }

    // Initialize OpenRouter client
    String apiKey = System.getenv("OPENROUTER_API_KEY");
    if (apiKey == null || apiKey.isBlank()) {
      throw new IllegalStateException(
          "OPENROUTER_API_KEY environment variable not set. "
              + "Set it to your OpenRouter API key to run this experiment.");
    }

    OpenRouterClient llmClient = new OpenRouterClient(apiKey);

    // Generate synthetic bars for backtesting
    BarSeries barSeries = BacktestPipeline.generateSyntheticBars(DEFAULT_BAR_COUNT, 42L);
    logger.info("Generated " + barSeries.getBarCount() + " synthetic bars for backtesting");

    // Run experiment
    ExperimentRunner runner = new ExperimentRunner(llmClient, fewShot, allStrategies);
    ExperimentRunner.ExperimentResults results = runner.run(numSpecs, barSeries, TEMPERATURE);

    // Print report
    String report = results.generateReport();
    System.out.println(report);

    // Save results
    ResultsStorage storage = new ResultsStorage(Path.of(outputDir));
    storage.saveResults(results);
    logger.info("Results saved to " + outputDir);

    return results;
  }
}
