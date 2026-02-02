package com.verlumen.tradestream.strategies.configurable;

import static com.google.common.truth.Truth.assertThat;
import static org.junit.Assert.assertThrows;

import java.time.Duration;
import java.time.ZonedDateTime;
import java.util.HashMap;
import java.util.Map;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.ta4j.core.BaseBar;
import org.ta4j.core.BaseBarSeries;
import org.ta4j.core.Indicator;
import org.ta4j.core.Rule;
import org.ta4j.core.indicators.SMAIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.num.Num;

@RunWith(JUnit4.class)
public class RuleRegistryTest {
  private RuleRegistry registry;
  private BaseBarSeries series;
  private Map<String, Indicator<Num>> indicators;

  @Before
  public void setUp() {
    registry = RuleRegistry.defaultRegistry();
    series = new BaseBarSeries();
    ZonedDateTime now = ZonedDateTime.now();
    for (int i = 0; i < 100; i++) {
      double price = 100 + Math.sin(i * 0.1) * 20;
      series.addBar(
          new BaseBar(
              Duration.ofMinutes(1),
              now.plusMinutes(i),
              price,
              price + 2,
              price - 2,
              price,
              1000.0));
    }
    indicators = new HashMap<>();
    ClosePriceIndicator closePrice = new ClosePriceIndicator(series);
    indicators.put("close", closePrice);
    indicators.put("sma_short", new SMAIndicator(closePrice, 10));
    indicators.put("sma_long", new SMAIndicator(closePrice, 20));
  }

  @Test
  public void defaultRegistry_hasCommonRuleTypes() {
    assertThat(registry.hasRule("CROSSOVER")).isTrue();
    assertThat(registry.hasRule("CROSSED_UP")).isTrue();
    assertThat(registry.hasRule("CROSSED_DOWN")).isTrue();
    assertThat(registry.hasRule("ABOVE")).isTrue();
    assertThat(registry.hasRule("BELOW")).isTrue();
    assertThat(registry.hasRule("IS_RISING")).isTrue();
    assertThat(registry.hasRule("IS_FALLING")).isTrue();
    assertThat(registry.hasRule("STOP_GAIN")).isTrue();
    assertThat(registry.hasRule("STOP_LOSS")).isTrue();
  }

  @Test
  public void hasRule_caseInsensitive() {
    assertThat(registry.hasRule("crossover")).isTrue();
    assertThat(registry.hasRule("CROSSOVER")).isTrue();
    assertThat(registry.hasRule("Crossover")).isTrue();
  }

  @Test
  public void hasRule_returnsFalse_forUnknownType() {
    assertThat(registry.hasRule("UNKNOWN_RULE")).isFalse();
  }

  @Test
  public void create_crossoverUp_returnsRule() {
    Map<String, Object> params = new HashMap<>();
    params.put("indicator", "sma_short");
    params.put("crosses", "sma_long");
    params.put("direction", "UP");

    Rule rule = registry.create("CROSSOVER", series, indicators, new ResolvedParams(params));
    assertThat(rule).isNotNull();
  }

  @Test
  public void create_crossoverDown_returnsRule() {
    Map<String, Object> params = new HashMap<>();
    params.put("indicator", "sma_short");
    params.put("crosses", "sma_long");
    params.put("direction", "DOWN");

    Rule rule = registry.create("CROSSOVER", series, indicators, new ResolvedParams(params));
    assertThat(rule).isNotNull();
  }

  @Test
  public void create_crossedUp_withIndicator_returnsRule() {
    Map<String, Object> params = new HashMap<>();
    params.put("indicator", "sma_short");
    params.put("crosses", "sma_long");

    Rule rule = registry.create("CROSSED_UP", series, indicators, new ResolvedParams(params));
    assertThat(rule).isNotNull();
  }

  @Test
  public void create_crossedUp_withValue_returnsRule() {
    Map<String, Object> params = new HashMap<>();
    params.put("indicator", "close");
    params.put("value", 100.0);

    Rule rule = registry.create("CROSSED_UP", series, indicators, new ResolvedParams(params));
    assertThat(rule).isNotNull();
  }

  @Test
  public void create_crossedDown_withIndicator_returnsRule() {
    Map<String, Object> params = new HashMap<>();
    params.put("indicator", "sma_short");
    params.put("crosses", "sma_long");

    Rule rule = registry.create("CROSSED_DOWN", series, indicators, new ResolvedParams(params));
    assertThat(rule).isNotNull();
  }

  @Test
  public void create_crossedDown_withValue_returnsRule() {
    Map<String, Object> params = new HashMap<>();
    params.put("indicator", "close");
    params.put("value", 100.0);

    Rule rule = registry.create("CROSSED_DOWN", series, indicators, new ResolvedParams(params));
    assertThat(rule).isNotNull();
  }

  @Test
  public void create_above_withOther_returnsRule() {
    Map<String, Object> params = new HashMap<>();
    params.put("indicator", "sma_short");
    params.put("other", "sma_long");

    Rule rule = registry.create("ABOVE", series, indicators, new ResolvedParams(params));
    assertThat(rule).isNotNull();
  }

  @Test
  public void create_above_withValue_returnsRule() {
    Map<String, Object> params = new HashMap<>();
    params.put("indicator", "close");
    params.put("value", 100.0);

    Rule rule = registry.create("ABOVE", series, indicators, new ResolvedParams(params));
    assertThat(rule).isNotNull();
  }

  @Test
  public void create_below_withOther_returnsRule() {
    Map<String, Object> params = new HashMap<>();
    params.put("indicator", "sma_short");
    params.put("other", "sma_long");

    Rule rule = registry.create("BELOW", series, indicators, new ResolvedParams(params));
    assertThat(rule).isNotNull();
  }

  @Test
  public void create_below_withValue_returnsRule() {
    Map<String, Object> params = new HashMap<>();
    params.put("indicator", "close");
    params.put("value", 100.0);

    Rule rule = registry.create("BELOW", series, indicators, new ResolvedParams(params));
    assertThat(rule).isNotNull();
  }

  @Test
  public void create_isRising_returnsRule() {
    Map<String, Object> params = new HashMap<>();
    params.put("indicator", "close");
    params.put("barCount", 5);

    Rule rule = registry.create("IS_RISING", series, indicators, new ResolvedParams(params));
    assertThat(rule).isNotNull();
  }

  @Test
  public void create_isFalling_returnsRule() {
    Map<String, Object> params = new HashMap<>();
    params.put("indicator", "close");
    params.put("barCount", 5);

    Rule rule = registry.create("IS_FALLING", series, indicators, new ResolvedParams(params));
    assertThat(rule).isNotNull();
  }

  @Test
  public void create_stopGain_returnsRule() {
    Map<String, Object> params = new HashMap<>();
    params.put("percentage", 5.0);

    Rule rule = registry.create("STOP_GAIN", series, indicators, new ResolvedParams(params));
    assertThat(rule).isNotNull();
  }

  @Test
  public void create_stopLoss_returnsRule() {
    Map<String, Object> params = new HashMap<>();
    params.put("percentage", 2.0);

    Rule rule = registry.create("STOP_LOSS", series, indicators, new ResolvedParams(params));
    assertThat(rule).isNotNull();
  }

  @Test
  public void create_trailingStopLoss_returnsRule() {
    Map<String, Object> params = new HashMap<>();
    params.put("percentage", 3.0);

    Rule rule =
        registry.create("TRAILING_STOP_LOSS", series, indicators, new ResolvedParams(params));
    assertThat(rule).isNotNull();
  }

  @Test
  public void create_throwsException_forUnknownType() {
    Map<String, Object> params = new HashMap<>();
    assertThrows(
        IllegalArgumentException.class,
        () -> registry.create("UNKNOWN", series, indicators, new ResolvedParams(params)));
  }

  @Test
  public void create_throwsException_forMissingIndicator() {
    Map<String, Object> params = new HashMap<>();
    params.put("indicator", "nonexistent");
    params.put("value", 100.0);

    assertThrows(
        IllegalArgumentException.class,
        () -> registry.create("CROSSED_UP", series, indicators, new ResolvedParams(params)));
  }

  @Test
  public void register_addsNewRuleType() {
    registry.register(
        "CUSTOM_RULE",
        (s, ind, p) -> {
          return new org.ta4j.core.rules.BooleanRule(true);
        });
    assertThat(registry.hasRule("CUSTOM_RULE")).isTrue();
  }

  @Test
  public void create_over_withOther_returnsRule() {
    Map<String, Object> params = new HashMap<>();
    params.put("indicator", "sma_short");
    params.put("other", "sma_long");

    Rule rule = registry.create("OVER", series, indicators, new ResolvedParams(params));
    assertThat(rule).isNotNull();
  }

  @Test
  public void create_under_withOther_returnsRule() {
    Map<String, Object> params = new HashMap<>();
    params.put("indicator", "sma_short");
    params.put("other", "sma_long");

    Rule rule = registry.create("UNDER", series, indicators, new ResolvedParams(params));
    assertThat(rule).isNotNull();
  }

  @Test
  public void create_overConstant_returnsRule() {
    Map<String, Object> params = new HashMap<>();
    params.put("indicator", "close");
    params.put("threshold", 100.0);

    Rule rule = registry.create("OVER_CONSTANT", series, indicators, new ResolvedParams(params));
    assertThat(rule).isNotNull();
  }

  @Test
  public void create_underConstant_returnsRule() {
    Map<String, Object> params = new HashMap<>();
    params.put("indicator", "close");
    params.put("threshold", 100.0);

    Rule rule = registry.create("UNDER_CONSTANT", series, indicators, new ResolvedParams(params));
    assertThat(rule).isNotNull();
  }

  @Test
  public void create_crossesAbove_returnsRule() {
    Map<String, Object> params = new HashMap<>();
    params.put("indicator", "close");
    params.put("value", 100.0);

    Rule rule = registry.create("CROSSES_ABOVE", series, indicators, new ResolvedParams(params));
    assertThat(rule).isNotNull();
  }

  @Test
  public void create_crossesBelow_returnsRule() {
    Map<String, Object> params = new HashMap<>();
    params.put("indicator", "close");
    params.put("value", 100.0);

    Rule rule = registry.create("CROSSES_BELOW", series, indicators, new ResolvedParams(params));
    assertThat(rule).isNotNull();
  }
}
