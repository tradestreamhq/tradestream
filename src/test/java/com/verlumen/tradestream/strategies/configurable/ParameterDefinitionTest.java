package com.verlumen.tradestream.strategies.configurable;

import static org.junit.Assert.*;

import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;

@RunWith(JUnit4.class)
public class ParameterDefinitionTest {

  @Test
  public void builder_createsCorrectDefinition() {
    ParameterDefinition def =
        ParameterDefinition.builder()
            .name("period")
            .type(ParameterType.INTEGER)
            .min(1)
            .max(100)
            .defaultValue(14)
            .build();

    assertEquals("period", def.getName());
    assertEquals(ParameterType.INTEGER, def.getType());
    assertEquals(1, def.getMin());
    assertEquals(100, def.getMax());
    assertEquals(14, def.getDefaultValue());
  }

  @Test
  public void constructor_createsCorrectDefinition() {
    ParameterDefinition def =
        new ParameterDefinition("threshold", ParameterType.DOUBLE, 0.1, 1.0, 0.5);

    assertEquals("threshold", def.getName());
    assertEquals(ParameterType.DOUBLE, def.getType());
    assertEquals(0.1, def.getMin());
    assertEquals(1.0, def.getMax());
    assertEquals(0.5, def.getDefaultValue());
  }

  @Test
  public void defaultConstructor_createsEmptyDefinition() {
    ParameterDefinition def = new ParameterDefinition();
    assertNull(def.getName());
    assertNull(def.getType());
    assertNull(def.getMin());
    assertNull(def.getMax());
    assertNull(def.getDefaultValue());
  }

  @Test
  public void setters_updateFields() {
    ParameterDefinition def = new ParameterDefinition();
    def.setName("ema");
    def.setType(ParameterType.INTEGER);
    def.setMin(5);
    def.setMax(50);
    def.setDefaultValue(20);

    assertEquals("ema", def.getName());
    assertEquals(ParameterType.INTEGER, def.getType());
    assertEquals(5, def.getMin());
    assertEquals(50, def.getMax());
    assertEquals(20, def.getDefaultValue());
  }

  @Test
  public void equals_sameValues_returnsTrue() {
    ParameterDefinition a = new ParameterDefinition("p", ParameterType.INTEGER, 1, 10, 5);
    ParameterDefinition b = new ParameterDefinition("p", ParameterType.INTEGER, 1, 10, 5);
    assertEquals(a, b);
    assertEquals(a.hashCode(), b.hashCode());
  }

  @Test
  public void equals_differentValues_returnsFalse() {
    ParameterDefinition a = new ParameterDefinition("p", ParameterType.INTEGER, 1, 10, 5);
    ParameterDefinition b = new ParameterDefinition("q", ParameterType.INTEGER, 1, 10, 5);
    assertNotEquals(a, b);
  }

  @Test
  public void equals_null_returnsFalse() {
    ParameterDefinition a = new ParameterDefinition("p", ParameterType.INTEGER, 1, 10, 5);
    assertNotEquals(a, null);
  }

  @Test
  public void equals_sameInstance_returnsTrue() {
    ParameterDefinition a = new ParameterDefinition("p", ParameterType.INTEGER, 1, 10, 5);
    assertEquals(a, a);
  }

  @Test
  public void toString_containsFieldValues() {
    ParameterDefinition def =
        new ParameterDefinition("period", ParameterType.INTEGER, 1, 100, 14);
    String str = def.toString();
    assertTrue(str.contains("period"));
    assertTrue(str.contains("INTEGER"));
    assertTrue(str.contains("1"));
    assertTrue(str.contains("100"));
    assertTrue(str.contains("14"));
  }
}
