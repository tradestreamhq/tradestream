package com.verlumen.tradestream.strategies.configurable;

import static com.google.common.truth.Truth.assertThat;

import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;

@RunWith(JUnit4.class)
public class ParameterDefinitionTest {

  @Test
  public void defaultConstructor_createsEmptyDefinition() {
    ParameterDefinition param = new ParameterDefinition();
    assertThat(param.getName()).isNull();
    assertThat(param.getType()).isNull();
    assertThat(param.getMin()).isNull();
    assertThat(param.getMax()).isNull();
    assertThat(param.getDefaultValue()).isNull();
  }

  @Test
  public void fullConstructor_setsAllFields() {
    ParameterDefinition param =
        new ParameterDefinition("period", ParameterType.INTEGER, 5, 50, 14);

    assertThat(param.getName()).isEqualTo("period");
    assertThat(param.getType()).isEqualTo(ParameterType.INTEGER);
    assertThat(param.getMin()).isEqualTo(5);
    assertThat(param.getMax()).isEqualTo(50);
    assertThat(param.getDefaultValue()).isEqualTo(14);
  }

  @Test
  public void setters_updateFields() {
    ParameterDefinition param = new ParameterDefinition();

    param.setName("threshold");
    param.setType(ParameterType.DOUBLE);
    param.setMin(0.0);
    param.setMax(100.0);
    param.setDefaultValue(50.0);

    assertThat(param.getName()).isEqualTo("threshold");
    assertThat(param.getType()).isEqualTo(ParameterType.DOUBLE);
    assertThat(param.getMin()).isEqualTo(0.0);
    assertThat(param.getMax()).isEqualTo(100.0);
    assertThat(param.getDefaultValue()).isEqualTo(50.0);
  }

  @Test
  public void builder_createsDefinition() {
    ParameterDefinition param =
        ParameterDefinition.builder()
            .name("multiplier")
            .type(ParameterType.DOUBLE)
            .min(0.5)
            .max(3.0)
            .defaultValue(1.0)
            .build();

    assertThat(param.getName()).isEqualTo("multiplier");
    assertThat(param.getType()).isEqualTo(ParameterType.DOUBLE);
    assertThat(param.getMin()).isEqualTo(0.5);
    assertThat(param.getMax()).isEqualTo(3.0);
    assertThat(param.getDefaultValue()).isEqualTo(1.0);
  }

  @Test
  public void equals_sameValues_returnsTrue() {
    ParameterDefinition param1 =
        ParameterDefinition.builder()
            .name("period")
            .type(ParameterType.INTEGER)
            .min(5)
            .max(50)
            .defaultValue(14)
            .build();
    ParameterDefinition param2 =
        ParameterDefinition.builder()
            .name("period")
            .type(ParameterType.INTEGER)
            .min(5)
            .max(50)
            .defaultValue(14)
            .build();

    assertThat(param1).isEqualTo(param2);
  }

  @Test
  public void equals_differentName_returnsFalse() {
    ParameterDefinition param1 = ParameterDefinition.builder().name("period1").build();
    ParameterDefinition param2 = ParameterDefinition.builder().name("period2").build();

    assertThat(param1).isNotEqualTo(param2);
  }

  @Test
  public void equals_differentType_returnsFalse() {
    ParameterDefinition param1 =
        ParameterDefinition.builder().name("param").type(ParameterType.INTEGER).build();
    ParameterDefinition param2 =
        ParameterDefinition.builder().name("param").type(ParameterType.DOUBLE).build();

    assertThat(param1).isNotEqualTo(param2);
  }

  @Test
  public void equals_null_returnsFalse() {
    ParameterDefinition param = ParameterDefinition.builder().name("test").build();
    assertThat(param.equals(null)).isFalse();
  }

  @Test
  public void equals_sameInstance_returnsTrue() {
    ParameterDefinition param = ParameterDefinition.builder().name("test").build();
    assertThat(param).isEqualTo(param);
  }

  @Test
  public void equals_differentClass_returnsFalse() {
    ParameterDefinition param = ParameterDefinition.builder().name("test").build();
    assertThat(param.equals("not a param")).isFalse();
  }

  @Test
  public void hashCode_sameValues_returnsSameHash() {
    ParameterDefinition param1 =
        ParameterDefinition.builder().name("period").type(ParameterType.INTEGER).build();
    ParameterDefinition param2 =
        ParameterDefinition.builder().name("period").type(ParameterType.INTEGER).build();

    assertThat(param1.hashCode()).isEqualTo(param2.hashCode());
  }

  @Test
  public void toString_containsName() {
    ParameterDefinition param = ParameterDefinition.builder().name("myParam").build();
    assertThat(param.toString()).contains("myParam");
  }

  @Test
  public void toString_containsAllFields() {
    ParameterDefinition param =
        ParameterDefinition.builder()
            .name("period")
            .type(ParameterType.INTEGER)
            .min(5)
            .max(50)
            .defaultValue(14)
            .build();

    String str = param.toString();
    assertThat(str).contains("name='period'");
    assertThat(str).contains("type=INTEGER");
    assertThat(str).contains("min=5");
    assertThat(str).contains("max=50");
    assertThat(str).contains("defaultValue=14");
  }

  @Test
  public void integerType_handlesIntValues() {
    ParameterDefinition param =
        ParameterDefinition.builder()
            .name("count")
            .type(ParameterType.INTEGER)
            .min(1)
            .max(100)
            .defaultValue(10)
            .build();

    assertThat(param.getMin().intValue()).isEqualTo(1);
    assertThat(param.getMax().intValue()).isEqualTo(100);
    assertThat(param.getDefaultValue().intValue()).isEqualTo(10);
  }

  @Test
  public void doubleType_handlesDoubleValues() {
    ParameterDefinition param =
        ParameterDefinition.builder()
            .name("ratio")
            .type(ParameterType.DOUBLE)
            .min(0.1)
            .max(0.9)
            .defaultValue(0.5)
            .build();

    assertThat(param.getMin().doubleValue()).isWithin(0.001).of(0.1);
    assertThat(param.getMax().doubleValue()).isWithin(0.001).of(0.9);
    assertThat(param.getDefaultValue().doubleValue()).isWithin(0.001).of(0.5);
  }
}
