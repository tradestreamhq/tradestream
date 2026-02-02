package com.verlumen.tradestream.strategies.configurable;

import static com.google.common.truth.Truth.assertThat;

import java.util.HashMap;
import java.util.Map;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;

@RunWith(JUnit4.class)
public class ConditionConfigTest {

  @Test
  public void defaultConstructor_createsEmptyConfig() {
    ConditionConfig config = new ConditionConfig();
    assertThat(config.getType()).isNull();
    assertThat(config.getIndicator()).isNull();
    assertThat(config.getParams()).isNull();
  }

  @Test
  public void fullConstructor_setsAllFields() {
    Map<String, Object> params = new HashMap<>();
    params.put("value", 70.0);

    ConditionConfig config = new ConditionConfig("CROSSED_UP", "rsi", params);

    assertThat(config.getType()).isEqualTo("CROSSED_UP");
    assertThat(config.getIndicator()).isEqualTo("rsi");
    assertThat(config.getParams()).containsEntry("value", 70.0);
  }

  @Test
  public void setters_updateFields() {
    ConditionConfig config = new ConditionConfig();

    Map<String, Object> params = new HashMap<>();
    params.put("crosses", "sma_long");

    config.setType("CROSSOVER");
    config.setIndicator("sma_short");
    config.setParams(params);

    assertThat(config.getType()).isEqualTo("CROSSOVER");
    assertThat(config.getIndicator()).isEqualTo("sma_short");
    assertThat(config.getParams()).containsEntry("crosses", "sma_long");
  }

  @Test
  public void builder_createsConfig() {
    Map<String, Object> params = new HashMap<>();
    params.put("value", 30.0);

    ConditionConfig config =
        ConditionConfig.builder()
            .type("CROSSED_DOWN")
            .indicator("rsi")
            .params(params)
            .build();

    assertThat(config.getType()).isEqualTo("CROSSED_DOWN");
    assertThat(config.getIndicator()).isEqualTo("rsi");
    assertThat(config.getParams()).containsEntry("value", 30.0);
  }

  @Test
  public void equals_sameValues_returnsTrue() {
    Map<String, Object> params = new HashMap<>();
    params.put("value", 70.0);

    ConditionConfig config1 =
        ConditionConfig.builder().type("CROSSED_UP").indicator("rsi").params(params).build();
    ConditionConfig config2 =
        ConditionConfig.builder().type("CROSSED_UP").indicator("rsi").params(params).build();

    assertThat(config1).isEqualTo(config2);
  }

  @Test
  public void equals_differentType_returnsFalse() {
    ConditionConfig config1 =
        ConditionConfig.builder().type("CROSSED_UP").indicator("rsi").build();
    ConditionConfig config2 =
        ConditionConfig.builder().type("CROSSED_DOWN").indicator("rsi").build();

    assertThat(config1).isNotEqualTo(config2);
  }

  @Test
  public void equals_differentIndicator_returnsFalse() {
    ConditionConfig config1 =
        ConditionConfig.builder().type("CROSSED_UP").indicator("rsi").build();
    ConditionConfig config2 =
        ConditionConfig.builder().type("CROSSED_UP").indicator("macd").build();

    assertThat(config1).isNotEqualTo(config2);
  }

  @Test
  public void equals_null_returnsFalse() {
    ConditionConfig config = ConditionConfig.builder().type("TEST").build();
    assertThat(config.equals(null)).isFalse();
  }

  @Test
  public void equals_sameInstance_returnsTrue() {
    ConditionConfig config = ConditionConfig.builder().type("TEST").build();
    assertThat(config).isEqualTo(config);
  }

  @Test
  public void equals_differentClass_returnsFalse() {
    ConditionConfig config = ConditionConfig.builder().type("TEST").build();
    assertThat(config.equals("not a config")).isFalse();
  }

  @Test
  public void hashCode_sameValues_returnsSameHash() {
    ConditionConfig config1 =
        ConditionConfig.builder().type("CROSSED_UP").indicator("rsi").build();
    ConditionConfig config2 =
        ConditionConfig.builder().type("CROSSED_UP").indicator("rsi").build();

    assertThat(config1.hashCode()).isEqualTo(config2.hashCode());
  }

  @Test
  public void toString_containsType() {
    ConditionConfig config = ConditionConfig.builder().type("CROSSOVER").build();
    assertThat(config.toString()).contains("CROSSOVER");
  }

  @Test
  public void toString_containsAllFields() {
    Map<String, Object> params = new HashMap<>();
    params.put("value", 70.0);

    ConditionConfig config =
        ConditionConfig.builder()
            .type("CROSSED_UP")
            .indicator("rsi")
            .params(params)
            .build();

    String str = config.toString();
    assertThat(str).contains("type='CROSSED_UP'");
    assertThat(str).contains("indicator='rsi'");
    assertThat(str).contains("params=");
  }

  @Test
  public void params_canContainMixedTypes() {
    Map<String, Object> params = new HashMap<>();
    params.put("value", 70.0);
    params.put("barCount", 5);
    params.put("direction", "UP");

    ConditionConfig config =
        ConditionConfig.builder().type("CUSTOM").indicator("ind").params(params).build();

    assertThat(config.getParams()).containsEntry("value", 70.0);
    assertThat(config.getParams()).containsEntry("barCount", 5);
    assertThat(config.getParams()).containsEntry("direction", "UP");
  }

  @Test
  public void params_canBeEmpty() {
    ConditionConfig config =
        ConditionConfig.builder()
            .type("STOP_LOSS")
            .params(new HashMap<>())
            .build();

    assertThat(config.getParams()).isEmpty();
  }
}
