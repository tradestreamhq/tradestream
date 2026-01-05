package com.verlumen.tradestream.strategies.configurable;

import static org.junit.Assert.*;

import java.util.List;
import org.junit.Test;

/** Tests for StrategyConfigLoader verifying YAML and JSON parsing. */
public class StrategyConfigLoaderTest {

  private static final String YAML_CONTENT =
      "name: SMA_EMA_CROSSOVER\n"
          + "description: Simple Moving Average crosses Exponential Moving Average\n"
          + "complexity: SIMPLE\n"
          + "parameterMessageType:"
          + " com.verlumen.tradestream.strategies.SmaEmaCrossoverParameters\n"
          + "\n"
          + "indicators:\n"
          + "  - id: sma\n"
          + "    type: SMA\n"
          + "    input: close\n"
          + "    params:\n"
          + "      period: \"${smaPeriod}\"\n"
          + "  - id: ema\n"
          + "    type: EMA\n"
          + "    input: close\n"
          + "    params:\n"
          + "      period: \"${emaPeriod}\"\n"
          + "\n"
          + "entryConditions:\n"
          + "  - type: CROSSED_UP\n"
          + "    indicator: sma\n"
          + "    params:\n"
          + "      crosses: ema\n"
          + "\n"
          + "exitConditions:\n"
          + "  - type: CROSSED_DOWN\n"
          + "    indicator: sma\n"
          + "    params:\n"
          + "      crosses: ema\n"
          + "\n"
          + "parameters:\n"
          + "  - name: smaPeriod\n"
          + "    type: INTEGER\n"
          + "    min: 5\n"
          + "    max: 50\n"
          + "    defaultValue: 20\n"
          + "  - name: emaPeriod\n"
          + "    type: INTEGER\n"
          + "    min: 5\n"
          + "    max: 50\n"
          + "    defaultValue: 50\n";

  @Test
  public void testParseYaml() {
    StrategyConfig config = StrategyConfigLoader.parseYaml(YAML_CONTENT);

    assertNotNull("Config should not be null", config);
    assertEquals("SMA_EMA_CROSSOVER", config.getName());
    assertEquals(
        "Simple Moving Average crosses Exponential Moving Average", config.getDescription());
    assertEquals("SIMPLE", config.getComplexity());
    assertEquals(
        "com.verlumen.tradestream.strategies.SmaEmaCrossoverParameters",
        config.getParameterMessageType());
  }

  @Test
  public void testParseYamlIndicators() {
    StrategyConfig config = StrategyConfigLoader.parseYaml(YAML_CONTENT);

    List<IndicatorConfig> indicators = config.getIndicators();
    assertNotNull("Indicators should not be null", indicators);
    assertEquals(2, indicators.size());

    IndicatorConfig sma = indicators.get(0);
    assertEquals("sma", sma.getId());
    assertEquals("SMA", sma.getType());
    assertEquals("close", sma.getInput());
    assertEquals("${smaPeriod}", sma.getParams().get("period"));

    IndicatorConfig ema = indicators.get(1);
    assertEquals("ema", ema.getId());
    assertEquals("EMA", ema.getType());
    assertEquals("close", ema.getInput());
    assertEquals("${emaPeriod}", ema.getParams().get("period"));
  }

  @Test
  public void testParseYamlConditions() {
    StrategyConfig config = StrategyConfigLoader.parseYaml(YAML_CONTENT);

    List<ConditionConfig> entryConditions = config.getEntryConditions();
    assertNotNull("Entry conditions should not be null", entryConditions);
    assertEquals(1, entryConditions.size());

    ConditionConfig entry = entryConditions.get(0);
    assertEquals("CROSSED_UP", entry.getType());
    assertEquals("sma", entry.getIndicator());
    assertEquals("ema", entry.getParams().get("crosses"));

    List<ConditionConfig> exitConditions = config.getExitConditions();
    assertNotNull("Exit conditions should not be null", exitConditions);
    assertEquals(1, exitConditions.size());

    ConditionConfig exit = exitConditions.get(0);
    assertEquals("CROSSED_DOWN", exit.getType());
    assertEquals("sma", exit.getIndicator());
    assertEquals("ema", exit.getParams().get("crosses"));
  }

  @Test
  public void testParseYamlParameters() {
    StrategyConfig config = StrategyConfigLoader.parseYaml(YAML_CONTENT);

    List<ParameterDefinition> parameters = config.getParameters();
    assertNotNull("Parameters should not be null", parameters);
    assertEquals(2, parameters.size());

    ParameterDefinition smaPeriod = parameters.get(0);
    assertEquals("smaPeriod", smaPeriod.getName());
    assertEquals(ParameterType.INTEGER, smaPeriod.getType());
    assertEquals(5, smaPeriod.getMin().intValue());
    assertEquals(50, smaPeriod.getMax().intValue());
    assertEquals(20, smaPeriod.getDefaultValue().intValue());

    ParameterDefinition emaPeriod = parameters.get(1);
    assertEquals("emaPeriod", emaPeriod.getName());
    assertEquals(ParameterType.INTEGER, emaPeriod.getType());
    assertEquals(5, emaPeriod.getMin().intValue());
    assertEquals(50, emaPeriod.getMax().intValue());
    assertEquals(50, emaPeriod.getDefaultValue().intValue());
  }

  @Test
  public void testParseJsonEquivalent() {
    // Parse JSON with same structure
    String jsonContent =
        "{"
            + "\"name\": \"SMA_EMA_CROSSOVER\","
            + "\"description\": \"Simple Moving Average crosses Exponential Moving Average\","
            + "\"complexity\": \"SIMPLE\""
            + "}";

    StrategyConfig config = StrategyConfigLoader.parseJson(jsonContent);

    assertNotNull("Config should not be null", config);
    assertEquals("SMA_EMA_CROSSOVER", config.getName());
    assertEquals(
        "Simple Moving Average crosses Exponential Moving Average", config.getDescription());
    assertEquals("SIMPLE", config.getComplexity());
  }

  @Test
  public void testToJsonAndBack() {
    StrategyConfig original = StrategyConfigLoader.parseYaml(YAML_CONTENT);

    // Convert to JSON and back
    String json = StrategyConfigLoader.toJson(original);
    StrategyConfig restored = StrategyConfigLoader.parseJson(json);

    assertEquals(original.getName(), restored.getName());
    assertEquals(original.getDescription(), restored.getDescription());
    assertEquals(original.getComplexity(), restored.getComplexity());
    assertEquals(original.getParameterMessageType(), restored.getParameterMessageType());
    assertEquals(original.getIndicators().size(), restored.getIndicators().size());
    assertEquals(original.getEntryConditions().size(), restored.getEntryConditions().size());
    assertEquals(original.getExitConditions().size(), restored.getExitConditions().size());
    assertEquals(original.getParameters().size(), restored.getParameters().size());
  }
}
