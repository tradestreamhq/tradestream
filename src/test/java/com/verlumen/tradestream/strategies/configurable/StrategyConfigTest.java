package com.verlumen.tradestream.strategies.configurable;

import static com.google.common.truth.Truth.assertThat;

import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;

@RunWith(JUnit4.class)
public class StrategyConfigTest {

  @Test
  public void defaultConstructor_createsEmptyConfig() {
    StrategyConfig config = new StrategyConfig();
    assertThat(config.getName()).isNull();
    assertThat(config.getDescription()).isNull();
    assertThat(config.getComplexity()).isNull();
  }

  @Test
  public void fullConstructor_setsAllFields() {
    List<IndicatorConfig> indicators =
        Arrays.asList(IndicatorConfig.builder().id("sma").type("SMA").build());
    List<ConditionConfig> entryConditions =
        Arrays.asList(ConditionConfig.builder().type("CROSSED_UP").build());
    List<ConditionConfig> exitConditions =
        Arrays.asList(ConditionConfig.builder().type("CROSSED_DOWN").build());
    List<ParameterDefinition> parameters =
        Arrays.asList(ParameterDefinition.builder().name("period").build());

    StrategyConfig config =
        new StrategyConfig(
            "TEST_STRATEGY",
            "Test description",
            "SIMPLE",
            "TestParams",
            indicators,
            entryConditions,
            exitConditions,
            parameters);

    assertThat(config.getName()).isEqualTo("TEST_STRATEGY");
    assertThat(config.getDescription()).isEqualTo("Test description");
    assertThat(config.getComplexity()).isEqualTo("SIMPLE");
    assertThat(config.getParameterMessageType()).isEqualTo("TestParams");
    assertThat(config.getIndicators()).hasSize(1);
    assertThat(config.getEntryConditions()).hasSize(1);
    assertThat(config.getExitConditions()).hasSize(1);
    assertThat(config.getParameters()).hasSize(1);
  }

  @Test
  public void setters_updateFields() {
    StrategyConfig config = new StrategyConfig();

    config.setName("MY_STRATEGY");
    config.setDescription("My description");
    config.setComplexity("COMPLEX");
    config.setParameterMessageType("MyParams");
    config.setIndicators(Collections.emptyList());
    config.setEntryConditions(Collections.emptyList());
    config.setExitConditions(Collections.emptyList());
    config.setParameters(Collections.emptyList());

    assertThat(config.getName()).isEqualTo("MY_STRATEGY");
    assertThat(config.getDescription()).isEqualTo("My description");
    assertThat(config.getComplexity()).isEqualTo("COMPLEX");
    assertThat(config.getParameterMessageType()).isEqualTo("MyParams");
    assertThat(config.getIndicators()).isEmpty();
    assertThat(config.getEntryConditions()).isEmpty();
    assertThat(config.getExitConditions()).isEmpty();
    assertThat(config.getParameters()).isEmpty();
  }

  @Test
  public void builder_createsConfig() {
    StrategyConfig config =
        StrategyConfig.builder()
            .name("BUILDER_STRATEGY")
            .description("Built with builder")
            .complexity("MEDIUM")
            .parameterMessageType("BuilderParams")
            .indicators(Collections.emptyList())
            .entryConditions(Collections.emptyList())
            .exitConditions(Collections.emptyList())
            .parameters(Collections.emptyList())
            .build();

    assertThat(config.getName()).isEqualTo("BUILDER_STRATEGY");
    assertThat(config.getDescription()).isEqualTo("Built with builder");
    assertThat(config.getComplexity()).isEqualTo("MEDIUM");
    assertThat(config.getParameterMessageType()).isEqualTo("BuilderParams");
  }

  @Test
  public void equals_sameValues_returnsTrue() {
    StrategyConfig config1 =
        StrategyConfig.builder()
            .name("TEST")
            .description("desc")
            .complexity("SIMPLE")
            .build();
    StrategyConfig config2 =
        StrategyConfig.builder()
            .name("TEST")
            .description("desc")
            .complexity("SIMPLE")
            .build();

    assertThat(config1).isEqualTo(config2);
  }

  @Test
  public void equals_differentValues_returnsFalse() {
    StrategyConfig config1 = StrategyConfig.builder().name("TEST1").build();
    StrategyConfig config2 = StrategyConfig.builder().name("TEST2").build();

    assertThat(config1).isNotEqualTo(config2);
  }

  @Test
  public void equals_null_returnsFalse() {
    StrategyConfig config = StrategyConfig.builder().name("TEST").build();
    assertThat(config.equals(null)).isFalse();
  }

  @Test
  public void equals_sameInstance_returnsTrue() {
    StrategyConfig config = StrategyConfig.builder().name("TEST").build();
    assertThat(config).isEqualTo(config);
  }

  @Test
  public void equals_differentClass_returnsFalse() {
    StrategyConfig config = StrategyConfig.builder().name("TEST").build();
    assertThat(config.equals("not a config")).isFalse();
  }

  @Test
  public void hashCode_sameValues_returnsSameHash() {
    StrategyConfig config1 = StrategyConfig.builder().name("TEST").build();
    StrategyConfig config2 = StrategyConfig.builder().name("TEST").build();

    assertThat(config1.hashCode()).isEqualTo(config2.hashCode());
  }

  @Test
  public void toString_containsName() {
    StrategyConfig config = StrategyConfig.builder().name("MY_STRATEGY").build();
    assertThat(config.toString()).contains("MY_STRATEGY");
  }

  @Test
  public void toString_containsAllFields() {
    StrategyConfig config =
        StrategyConfig.builder()
            .name("TEST")
            .description("desc")
            .complexity("SIMPLE")
            .parameterMessageType("Params")
            .build();

    String str = config.toString();
    assertThat(str).contains("name='TEST'");
    assertThat(str).contains("description='desc'");
    assertThat(str).contains("complexity='SIMPLE'");
    assertThat(str).contains("parameterMessageType='Params'");
  }
}
