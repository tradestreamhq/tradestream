package com.verlumen.tradestream.strategies.configurable.llm;

import com.verlumen.tradestream.strategies.configurable.StrategyConfig;
import com.verlumen.tradestream.strategies.configurable.StrategyConfigLoader;
import java.util.List;

/**
 * Builds prompts for LLM-based strategy specification generation. Uses few-shot examples from
 * existing strategy configs to teach the LLM the YAML schema.
 */
public final class StrategySpecPromptTemplate {

  private static final String SYSTEM_PROMPT =
      "You are an expert quantitative trading strategy designer. Your task is to generate novel"
          + " trading strategy specifications in YAML format.\n\n"
          + "You have deep knowledge of technical analysis indicators and how to combine them"
          + " effectively. You understand:\n"
          + "- Moving averages (SMA, EMA, DEMA, TEMA, WMA, ZLEMA) for trend following\n"
          + "- Oscillators (RSI, Stochastic, MACD, CCI, CMO, Williams %R, ROC) for momentum\n"
          + "- Volume indicators (OBV, CMF, MFI, Klinger, Chaikin) for volume confirmation\n"
          + "- Trend indicators (ADX, DMI, Aroon, Parabolic SAR) for trend strength\n"
          + "- Volatility indicators (ATR, Bollinger Bands, Keltner Channels) for"
          + " range/breakout\n\n"
          + "When generating strategies:\n"
          + "1. Combine 2-4 indicators that complement each other\n"
          + "2. Use clear entry and exit conditions\n"
          + "3. Include meaningful parameter ranges for optimization\n"
          + "4. Avoid overly complex logic that may overfit\n"
          + "5. Consider both trend-following and mean-reversion approaches\n"
          + "6. Output ONLY valid YAML - no explanations, no markdown code blocks";

  private static final String SCHEMA_DOCS =
      "## Strategy YAML Schema\n\n"
          + "```yaml\n"
          + "name: STRATEGY_NAME  # Uppercase with underscores\n"
          + "description: Brief description of the strategy\n"
          + "complexity: SIMPLE|MEDIUM|COMPLEX\n\n"
          + "indicators:\n"
          + "  - id: unique_identifier\n"
          + "    type: INDICATOR_TYPE\n"
          + "    input: close|high|low|open|volume|<other_indicator_id>\n"
          + "    params:\n"
          + "      period: \"${parameterName}\"\n\n"
          + "entryConditions:\n"
          + "  - type: CONDITION_TYPE\n"
          + "    indicator: indicator_id\n"
          + "    params:\n"
          + "      crosses: other_indicator_id  # For crossovers\n"
          + "      threshold: 25  # For constant comparisons\n\n"
          + "exitConditions:\n"
          + "  - type: CONDITION_TYPE\n"
          + "    indicator: indicator_id\n"
          + "    params:\n"
          + "      crosses: other_indicator_id\n\n"
          + "parameters:\n"
          + "  - name: parameterName\n"
          + "    type: INTEGER|DOUBLE\n"
          + "    min: 5\n"
          + "    max: 50\n"
          + "    defaultValue: 20\n"
          + "```\n\n"
          + "## Available Indicator Types\n"
          + "SMA, EMA, DEMA, TEMA, WMA, ZLEMA, KAMA, RSI, MACD, STOCHASTIC_K, STOCHASTIC_D, "
          + "CCI, CMO, WILLIAMS_R, ROC, DPO, AWESOME_OSCILLATOR, ADX, PLUS_DI, MINUS_DI, "
          + "AROON_UP, AROON_DOWN, PARABOLIC_SAR, ATR, BOLLINGER_UPPER, BOLLINGER_LOWER, "
          + "BOLLINGER_MIDDLE, KELTNER_UPPER, KELTNER_LOWER, DONCHIAN_UPPER, DONCHIAN_LOWER, "
          + "OBV, CMF, MFI, AD, CHAIKIN_OSCILLATOR, KLINGER_VOLUME_OSCILLATOR, VWAP, PVT, NVI, "
          + "CLOSE, HIGH, LOW, OPEN, VOLUME, TYPICAL_PRICE, MEDIAN_PRICE, STD_DEV, PREVIOUS, "
          + "CONSTANT, MASS_INDEX, TRIX, FRAMA\n\n"
          + "## Available Condition Types\n"
          + "CROSSED_UP, CROSSED_DOWN, OVER_CONSTANT, UNDER_CONSTANT, OVER_INDICATOR, "
          + "UNDER_INDICATOR, CROSSED_UP_CONSTANT, CROSSED_DOWN_CONSTANT, IS_RISING, IS_FALLING, "
          + "ABOVE, BELOW, OVER, UNDER, STOP_GAIN, STOP_LOSS, TRAILING_STOP_LOSS\n\n"
          + "## Available Parameter Types\n"
          + "INTEGER, DOUBLE";

  private static final String[] CREATIVITY_HINTS = {
    "Focus on volume confirmation for trend signals",
    "Combine momentum and trend indicators in a novel way",
    "Use multiple timeframe concepts with different period lengths",
    "Create a mean-reversion strategy with overbought/oversold filters",
    "Combine volatility breakout with trend confirmation",
    "Create a trend-following strategy with volatility-based filters",
    "Combine Aroon indicators with momentum oscillators",
    "Use CMO (Chande Momentum Oscillator) with trend filters",
    "Create a strategy using Williams %R with Bollinger Band confirmation",
    "Combine ADX trend strength with Stochastic momentum signals",
    "Use Keltner Channels with RSI for breakout confirmation",
    "Create a MACD-based strategy with volume confirmation using CMF",
    "Combine DEMA/TEMA crossovers with ADX trend filter",
    "Use ATR-based dynamic thresholds with momentum oscillators",
    "Create a DPO-based strategy with moving average confirmation"
  };

  private StrategySpecPromptTemplate() {}

  public static String getSystemPrompt() {
    return SYSTEM_PROMPT;
  }

  public static String buildUserPrompt(List<StrategyConfig> fewShotExamples, int creativityIndex) {
    StringBuilder sb = new StringBuilder();
    sb.append("Generate a NOVEL trading strategy specification in YAML format.\n\n");
    sb.append(SCHEMA_DOCS).append("\n\n");

    sb.append("## Few-Shot Examples\n");
    sb.append("Here are proven trading strategies to learn from:\n\n");

    for (int i = 0; i < fewShotExamples.size(); i++) {
      StrategyConfig config = fewShotExamples.get(i);
      String json = StrategyConfigLoader.toJson(config);
      sb.append("### Example ").append(i + 1).append(": ").append(config.getName()).append("\n");
      sb.append("```json\n").append(json).append("\n```\n\n");
    }

    sb.append("## Requirements\n");
    sb.append("1. Create a NOVEL strategy - do NOT copy any example directly\n");
    sb.append("2. Combine indicators in a new way not seen in the examples\n");
    sb.append("3. Use 2-4 indicators that complement each other\n");
    sb.append("4. Include clear entry and exit conditions\n");
    sb.append("5. Define meaningful parameter ranges (not too wide, not too narrow)\n");
    sb.append("6. The strategy should have a clear trading logic\n\n");

    String hint = CREATIVITY_HINTS[creativityIndex % CREATIVITY_HINTS.length];
    sb.append("## Creativity Hint\n").append(hint).append("\n\n");

    sb.append("## Output Format\n");
    sb.append(
        "Output ONLY valid YAML - no explanations, no markdown code blocks, "
            + "just the YAML content starting with 'name:'.\n");
    sb.append("Do NOT include 'parameterMessageType' field.\n");

    return sb.toString();
  }

  public static String getCreativityHint(int index) {
    return CREATIVITY_HINTS[index % CREATIVITY_HINTS.length];
  }

  public static int getCreativityHintCount() {
    return CREATIVITY_HINTS.length;
  }
}
