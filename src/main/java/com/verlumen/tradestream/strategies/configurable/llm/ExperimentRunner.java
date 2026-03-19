package com.verlumen.tradestream.strategies.configurable.llm;

import com.verlumen.tradestream.strategies.configurable.StrategyConfig;
import com.verlumen.tradestream.strategies.configurable.StrategyConfigLoader;
import java.io.IOException;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.logging.Level;
import java.util.logging.Logger;
import org.ta4j.core.BarSeries;

/**
 * Experiment runner for Phase 2 validation. Generates N strategy specs via LLM, validates them,
 * backtests each valid spec, and ranks results by performance metrics.
 */
public final class ExperimentRunner {
  private static final Logger logger = Logger.getLogger(ExperimentRunner.class.getName());

  private final OpenRouterClient llmClient;
  private final GeneratedSpecValidator validator;
  private final BacktestPipeline backtestPipeline;
  private final List<StrategyConfig> fewShotExamples;
  private final List<StrategyConfig> existingStrategies;

  public ExperimentRunner(
      OpenRouterClient llmClient,
      List<StrategyConfig> fewShotExamples,
      List<StrategyConfig> existingStrategies) {
    this.llmClient = llmClient;
    this.validator = new GeneratedSpecValidator();
    this.backtestPipeline = new BacktestPipeline();
    this.fewShotExamples = fewShotExamples;
    this.existingStrategies = existingStrategies;
  }

  /**
   * Run the full experiment: generate specs, validate, backtest, and rank.
   *
   * @param numSpecs Number of specs to generate
   * @param barSeries Bar series to backtest against
   * @param temperature LLM temperature
   * @return Experiment results
   */
  public ExperimentResults run(int numSpecs, BarSeries barSeries, double temperature) {
    List<GenerationAttempt> attempts = new ArrayList<>();
    List<StrategyConfig> allExisting = new ArrayList<>(existingStrategies);

    logger.info("Starting experiment: generating " + numSpecs + " specs");

    for (int i = 0; i < numSpecs; i++) {
      logger.info("Generating spec " + (i + 1) + "/" + numSpecs);

      GenerationAttempt attempt = generateAndValidate(i, allExisting, temperature);
      attempts.add(attempt);

      // Track successfully generated strategies for novelty checking
      if (attempt.config != null && attempt.validationReport.isValid()) {
        allExisting.add(attempt.config);
      }

      // Rate limit between API calls
      try {
        Thread.sleep(500);
      } catch (InterruptedException e) {
        Thread.currentThread().interrupt();
        break;
      }
    }

    // Backtest all valid specs
    List<BacktestPipeline.BacktestResult> backtestResults = new ArrayList<>();
    List<StrategyConfig> validConfigs = new ArrayList<>();

    for (GenerationAttempt attempt : attempts) {
      if (attempt.config != null && attempt.validationReport.isValid()) {
        validConfigs.add(attempt.config);
        BacktestPipeline.BacktestResult result =
            backtestPipeline.runBacktest(attempt.config, barSeries);
        backtestResults.add(result);
        logger.info("  Backtest: " + result);
      }
    }

    // Rank by Sharpe (return over max drawdown)
    List<RankedStrategy> ranked = new ArrayList<>();
    for (int i = 0; i < validConfigs.size(); i++) {
      ranked.add(new RankedStrategy(validConfigs.get(i), backtestResults.get(i)));
    }
    ranked.sort(Comparator.comparingDouble(r -> -r.backtestResult.getSharpeApprox()));

    return new ExperimentResults(attempts, backtestResults, ranked);
  }

  private GenerationAttempt generateAndValidate(
      int index, List<StrategyConfig> allExisting, double temperature) {

    long startMs = System.currentTimeMillis();
    String rawYaml;

    try {
      String systemPrompt = StrategySpecPromptTemplate.getSystemPrompt();
      String userPrompt =
          StrategySpecPromptTemplate.buildUserPrompt(fewShotExamples, index);

      rawYaml = llmClient.chatCompletion(systemPrompt, userPrompt, temperature, 2000);
    } catch (IOException | InterruptedException e) {
      logger.log(Level.WARNING, "LLM call failed for spec " + index, e);
      return new GenerationAttempt(
          index,
          null,
          null,
          new GeneratedSpecValidator.ValidationReport(
              false, false, false, false, List.of("LLM call failed: " + e.getMessage()), List.of()),
          System.currentTimeMillis() - startMs,
          StrategySpecPromptTemplate.getCreativityHint(index));
    }

    long genTimeMs = System.currentTimeMillis() - startMs;

    // Parse
    StrategyConfig config = validator.parseYaml(rawYaml);
    if (config != null) {
      // Remove parameterMessageType if the LLM added it
      config.setParameterMessageType(null);
    }

    // Validate
    GeneratedSpecValidator.ValidationReport report = validator.validate(config, allExisting);

    String status = report.isValid() ? "VALID" : "INVALID";
    String name = config != null ? config.getName() : "<parse_failed>";
    logger.info(
        String.format(
            "  [%d] %s %s (syntax=%b, logic=%b, novel=%b) in %dms",
            index, status, name, report.isSyntaxValid(), report.isLogicValid(), report.isNovel(),
            genTimeMs));

    return new GenerationAttempt(
        index,
        rawYaml,
        config,
        report,
        genTimeMs,
        StrategySpecPromptTemplate.getCreativityHint(index));
  }

  /** Select diverse few-shot examples from all strategy configs. */
  public static List<StrategyConfig> selectDiverseExamples(
      List<StrategyConfig> allConfigs, int count) {
    List<StrategyConfig> selected = new ArrayList<>();
    java.util.Set<String> seenIndicatorCombos = new java.util.HashSet<>();

    for (StrategyConfig config : allConfigs) {
      if (config.getIndicators() == null) continue;

      List<String> types = new ArrayList<>();
      for (var ind : config.getIndicators()) {
        types.add(ind.getType());
      }
      java.util.Collections.sort(types);
      String combo = String.join(",", types);

      if (seenIndicatorCombos.add(combo)) {
        selected.add(config);
      }
      if (selected.size() >= count) break;
    }
    return selected;
  }

  /** Load all strategy configs from a directory. */
  public static List<StrategyConfig> loadAllStrategies(String dir) {
    return StrategyConfigLoader.loadAll(dir);
  }

  // --- Inner classes ---

  /** A single generation attempt. */
  public static final class GenerationAttempt {
    final int index;
    final String rawYaml;
    final StrategyConfig config;
    final GeneratedSpecValidator.ValidationReport validationReport;
    final long generationTimeMs;
    final String creativityHint;

    public GenerationAttempt(
        int index,
        String rawYaml,
        StrategyConfig config,
        GeneratedSpecValidator.ValidationReport validationReport,
        long generationTimeMs,
        String creativityHint) {
      this.index = index;
      this.rawYaml = rawYaml;
      this.config = config;
      this.validationReport = validationReport;
      this.generationTimeMs = generationTimeMs;
      this.creativityHint = creativityHint;
    }

    public int getIndex() {
      return index;
    }

    public String getRawYaml() {
      return rawYaml;
    }

    public StrategyConfig getConfig() {
      return config;
    }

    public GeneratedSpecValidator.ValidationReport getValidationReport() {
      return validationReport;
    }

    public long getGenerationTimeMs() {
      return generationTimeMs;
    }

    public String getCreativityHint() {
      return creativityHint;
    }
  }

  /** A strategy ranked by backtest performance. */
  public static final class RankedStrategy {
    final StrategyConfig config;
    final BacktestPipeline.BacktestResult backtestResult;

    public RankedStrategy(StrategyConfig config, BacktestPipeline.BacktestResult backtestResult) {
      this.config = config;
      this.backtestResult = backtestResult;
    }

    public StrategyConfig getConfig() {
      return config;
    }

    public BacktestPipeline.BacktestResult getBacktestResult() {
      return backtestResult;
    }
  }

  /** Full experiment results. */
  public static final class ExperimentResults {
    private final List<GenerationAttempt> attempts;
    private final List<BacktestPipeline.BacktestResult> backtestResults;
    private final List<RankedStrategy> rankedStrategies;

    public ExperimentResults(
        List<GenerationAttempt> attempts,
        List<BacktestPipeline.BacktestResult> backtestResults,
        List<RankedStrategy> rankedStrategies) {
      this.attempts = attempts;
      this.backtestResults = backtestResults;
      this.rankedStrategies = rankedStrategies;
    }

    public List<GenerationAttempt> getAttempts() {
      return attempts;
    }

    public List<BacktestPipeline.BacktestResult> getBacktestResults() {
      return backtestResults;
    }

    public List<RankedStrategy> getRankedStrategies() {
      return rankedStrategies;
    }

    public int getTotalGenerated() {
      return attempts.size();
    }

    public int getSyntaxValidCount() {
      return (int) attempts.stream().filter(a -> a.validationReport.isSyntaxValid()).count();
    }

    public int getLogicValidCount() {
      return (int) attempts.stream().filter(a -> a.validationReport.isLogicValid()).count();
    }

    public int getNovelCount() {
      return (int) attempts.stream().filter(a -> a.validationReport.isNovel()).count();
    }

    public int getFullyValidCount() {
      return (int) attempts.stream().filter(a -> a.validationReport.isValid()).count();
    }

    public int getSuccessfulBacktestCount() {
      return (int) backtestResults.stream().filter(BacktestPipeline.BacktestResult::isSuccessful).count();
    }

    public double getSyntaxValidRate() {
      return attempts.isEmpty() ? 0 : (double) getSyntaxValidCount() / attempts.size();
    }

    public double getLogicValidRate() {
      return attempts.isEmpty() ? 0 : (double) getLogicValidCount() / attempts.size();
    }

    public double getNovelRate() {
      return attempts.isEmpty() ? 0 : (double) getNovelCount() / attempts.size();
    }

    public String generateReport() {
      StringBuilder sb = new StringBuilder();
      sb.append("=" .repeat(60)).append("\n");
      sb.append("PHASE 2 VALIDATION: LLM Spec Generation + Backtesting\n");
      sb.append("=" .repeat(60)).append("\n\n");

      int total = getTotalGenerated();
      sb.append(String.format("Total Generated: %d%n", total));
      sb.append(String.format("Syntax Valid: %d/%d (%.1f%%) %s (target: 80%%)%n",
          getSyntaxValidCount(), total, getSyntaxValidRate() * 100,
          getSyntaxValidRate() >= 0.80 ? "PASS" : "FAIL"));
      sb.append(String.format("Logic Valid:  %d/%d (%.1f%%) %s (target: 60%%)%n",
          getLogicValidCount(), total, getLogicValidRate() * 100,
          getLogicValidRate() >= 0.60 ? "PASS" : "FAIL"));
      sb.append(String.format("Novel:        %d/%d (%.1f%%) %s (target: 70%%)%n",
          getNovelCount(), total, getNovelRate() * 100,
          getNovelRate() >= 0.70 ? "PASS" : "FAIL"));
      sb.append(String.format("Fully Valid:  %d/%d (%.1f%%)%n",
          getFullyValidCount(), total,
          total > 0 ? (double) getFullyValidCount() / total * 100 : 0));
      sb.append(String.format("Backtested:   %d%n", backtestResults.size()));
      sb.append(String.format("Successful:   %d%n", getSuccessfulBacktestCount()));

      boolean overallPass = getSyntaxValidRate() >= 0.80
          && getLogicValidRate() >= 0.60
          && getNovelRate() >= 0.70;
      sb.append(String.format("%nOVERALL: %s%n", overallPass ? "GO" : "NO-GO"));

      if (!rankedStrategies.isEmpty()) {
        sb.append("\n--- Top Strategies by Return/Drawdown ---\n");
        int rank = 1;
        for (RankedStrategy rs : rankedStrategies) {
          if (!rs.backtestResult.isSuccessful()) continue;
          sb.append(String.format(
              "#%d %s: return=%.4f sharpe=%.4f winRate=%.1f%% trades=%d vs_b&h=%.4f%n",
              rank++,
              rs.backtestResult.getStrategyName(),
              rs.backtestResult.getGrossReturn(),
              rs.backtestResult.getSharpeApprox(),
              rs.backtestResult.getWinRate() * 100,
              rs.backtestResult.getNumTrades(),
              rs.backtestResult.getVsBuyHoldRatio()));
          if (rank > 10) break;
        }
      }

      return sb.toString();
    }
  }
}
