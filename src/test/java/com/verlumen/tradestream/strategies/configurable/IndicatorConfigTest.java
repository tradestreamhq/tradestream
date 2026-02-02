package com.verlumen.tradestream.strategies.configurable;

import static com.google.common.truth.Truth.assertThat;

import java.util.HashMap;
import java.util.Map;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;

@RunWith(JUnit4.class)
public class IndicatorConfigTest {

  @Test
  public void defaultConstructor_createsEmptyConfig() {
    IndicatorConfig config = new IndicatorConfig();
    assertThat(config.getId()).isNull();
    assertThat(config.getType()).isNull();
    assertThat(config.getInput()).isNull();
    assertThat(config.getParams()).isNull();
  }

  @Test
  public void fullConstructor_setsAllFields() {
    Map<String, String> params = new HashMap<>();
    params.put("period", "14");

    IndicatorConfig config = new IndicatorConfig("rsi", "RSI", "close", params);

    assertThat(config.getId()).isEqualTo("rsi");
    assertThat(config.getType()).isEqualTo("RSI");
    assertThat(config.getInput()).isEqualTo("close");
    assertThat(config.getParams()).containsEntry("period", "14");
  }

  @Test
  public void setters_updateFields() {
    IndicatorConfig config = new IndicatorConfig();

    Map<String, String> params = new HashMap<>();
    params.put("short_period", "12");
    params.put("long_period", "26");

    config.setId("macd");
    config.setType("MACD");
    config.setInput("close");
    config.setParams(params);

    assertThat(config.getId()).isEqualTo("macd");
    assertThat(config.getType()).isEqualTo("MACD");
    assertThat(config.getInput()).isEqualTo("close");
    assertThat(config.getParams()).hasSize(2);
  }

  @Test
  public void builder_createsConfig() {
    Map<String, String> params = new HashMap<>();
    params.put("period", "20");

    IndicatorConfig config =
        IndicatorConfig.builder()
            .id("sma")
            .type("SMA")
            .input("close")
            .params(params)
            .build();

    assertThat(config.getId()).isEqualTo("sma");
    assertThat(config.getType()).isEqualTo("SMA");
    assertThat(config.getInput()).isEqualTo("close");
    assertThat(config.getParams()).containsEntry("period", "20");
  }

  @Test
  public void equals_sameValues_returnsTrue() {
    Map<String, String> params = new HashMap<>();
    params.put("period", "14");

    IndicatorConfig config1 =
        IndicatorConfig.builder().id("rsi").type("RSI").input("close").params(params).build();
    IndicatorConfig config2 =
        IndicatorConfig.builder().id("rsi").type("RSI").input("close").params(params).build();

    assertThat(config1).isEqualTo(config2);
  }

  @Test
  public void equals_differentId_returnsFalse() {
    IndicatorConfig config1 = IndicatorConfig.builder().id("rsi1").type("RSI").build();
    IndicatorConfig config2 = IndicatorConfig.builder().id("rsi2").type("RSI").build();

    assertThat(config1).isNotEqualTo(config2);
  }

  @Test
  public void equals_differentType_returnsFalse() {
    IndicatorConfig config1 = IndicatorConfig.builder().id("ind").type("SMA").build();
    IndicatorConfig config2 = IndicatorConfig.builder().id("ind").type("EMA").build();

    assertThat(config1).isNotEqualTo(config2);
  }

  @Test
  public void equals_null_returnsFalse() {
    IndicatorConfig config = IndicatorConfig.builder().id("test").build();
    assertThat(config.equals(null)).isFalse();
  }

  @Test
  public void equals_sameInstance_returnsTrue() {
    IndicatorConfig config = IndicatorConfig.builder().id("test").build();
    assertThat(config).isEqualTo(config);
  }

  @Test
  public void equals_differentClass_returnsFalse() {
    IndicatorConfig config = IndicatorConfig.builder().id("test").build();
    assertThat(config.equals("not a config")).isFalse();
  }

  @Test
  public void hashCode_sameValues_returnsSameHash() {
    IndicatorConfig config1 = IndicatorConfig.builder().id("rsi").type("RSI").build();
    IndicatorConfig config2 = IndicatorConfig.builder().id("rsi").type("RSI").build();

    assertThat(config1.hashCode()).isEqualTo(config2.hashCode());
  }

  @Test
  public void toString_containsId() {
    IndicatorConfig config = IndicatorConfig.builder().id("myIndicator").build();
    assertThat(config.toString()).contains("myIndicator");
  }

  @Test
  public void toString_containsAllFields() {
    Map<String, String> params = new HashMap<>();
    params.put("period", "14");

    IndicatorConfig config =
        IndicatorConfig.builder()
            .id("rsi")
            .type("RSI")
            .input("close")
            .params(params)
            .build();

    String str = config.toString();
    assertThat(str).contains("id='rsi'");
    assertThat(str).contains("type='RSI'");
    assertThat(str).contains("input='close'");
    assertThat(str).contains("params=");
  }

  @Test
  public void params_canBeEmpty() {
    IndicatorConfig config =
        IndicatorConfig.builder().id("close").type("CLOSE").params(new HashMap<>()).build();

    assertThat(config.getParams()).isEmpty();
  }

  @Test
  public void params_canContainMultipleEntries() {
    Map<String, String> params = new HashMap<>();
    params.put("short_period", "12");
    params.put("long_period", "26");
    params.put("signal_period", "9");

    IndicatorConfig config =
        IndicatorConfig.builder().id("macd").type("MACD").params(params).build();

    assertThat(config.getParams()).hasSize(3);
    assertThat(config.getParams()).containsEntry("short_period", "12");
    assertThat(config.getParams()).containsEntry("long_period", "26");
    assertThat(config.getParams()).containsEntry("signal_period", "9");
  }
}
