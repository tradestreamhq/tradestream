package com.verlumen.tradestream.strategies.configurable;

import static com.google.common.truth.Truth.assertThat;
import static org.junit.Assert.assertThrows;

import java.util.HashMap;
import java.util.Map;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;

@RunWith(JUnit4.class)
public class ResolvedParamsTest {
  private Map<String, Object> params;
  private ResolvedParams resolvedParams;

  @Before
  public void setUp() {
    params = new HashMap<>();
    params.put("intValue", 42);
    params.put("doubleValue", 3.14);
    params.put("stringValue", "hello");
    params.put("intAsString", "100");
    params.put("doubleAsString", "2.718");
    resolvedParams = new ResolvedParams(params);
  }

  @Test
  public void getInt_withIntegerValue_returnsInt() {
    assertThat(resolvedParams.getInt("intValue")).isEqualTo(42);
  }

  @Test
  public void getInt_withStringValue_parsesString() {
    assertThat(resolvedParams.getInt("intAsString")).isEqualTo(100);
  }

  @Test
  public void getInt_missingKey_throwsException() {
    assertThrows(IllegalArgumentException.class, () -> resolvedParams.getInt("nonexistent"));
  }

  @Test
  public void getInt_withDefault_returnsDefault_whenMissing() {
    assertThat(resolvedParams.getInt("nonexistent", 99)).isEqualTo(99);
  }

  @Test
  public void getInt_withDefault_returnsValue_whenPresent() {
    assertThat(resolvedParams.getInt("intValue", 99)).isEqualTo(42);
  }

  @Test
  public void getDouble_withDoubleValue_returnsDouble() {
    assertThat(resolvedParams.getDouble("doubleValue")).isWithin(0.001).of(3.14);
  }

  @Test
  public void getDouble_withStringValue_parsesString() {
    assertThat(resolvedParams.getDouble("doubleAsString")).isWithin(0.001).of(2.718);
  }

  @Test
  public void getDouble_withIntegerValue_convertsToDouble() {
    assertThat(resolvedParams.getDouble("intValue")).isWithin(0.001).of(42.0);
  }

  @Test
  public void getDouble_missingKey_throwsException() {
    assertThrows(IllegalArgumentException.class, () -> resolvedParams.getDouble("nonexistent"));
  }

  @Test
  public void getDouble_withDefault_returnsDefault_whenMissing() {
    assertThat(resolvedParams.getDouble("nonexistent", 1.5)).isWithin(0.001).of(1.5);
  }

  @Test
  public void getDouble_withDefault_returnsValue_whenPresent() {
    assertThat(resolvedParams.getDouble("doubleValue", 1.5)).isWithin(0.001).of(3.14);
  }

  @Test
  public void getString_returnsString() {
    assertThat(resolvedParams.getString("stringValue")).isEqualTo("hello");
  }

  @Test
  public void getString_withNumber_convertsToString() {
    assertThat(resolvedParams.getString("intValue")).isEqualTo("42");
  }

  @Test
  public void getString_missingKey_throwsException() {
    assertThrows(IllegalArgumentException.class, () -> resolvedParams.getString("nonexistent"));
  }

  @Test
  public void getString_withDefault_returnsDefault_whenMissing() {
    assertThat(resolvedParams.getString("nonexistent", "default")).isEqualTo("default");
  }

  @Test
  public void getString_withDefault_returnsValue_whenPresent() {
    assertThat(resolvedParams.getString("stringValue", "default")).isEqualTo("hello");
  }

  @Test
  public void containsKey_returnsTrue_whenKeyExists() {
    assertThat(resolvedParams.containsKey("intValue")).isTrue();
  }

  @Test
  public void containsKey_returnsFalse_whenKeyMissing() {
    assertThat(resolvedParams.containsKey("nonexistent")).isFalse();
  }

  @Test
  public void get_returnsRawValue() {
    assertThat(resolvedParams.get("intValue")).isEqualTo(42);
    assertThat(resolvedParams.get("stringValue")).isEqualTo("hello");
  }

  @Test
  public void get_returnsNull_whenKeyMissing() {
    assertThat(resolvedParams.get("nonexistent")).isNull();
  }

  @Test
  public void asMap_returnsCopyOfParams() {
    Map<String, Object> copy = resolvedParams.asMap();
    assertThat(copy).containsEntry("intValue", 42);
    assertThat(copy).containsEntry("stringValue", "hello");
  }

  @Test
  public void asMap_returnsImmutableCopy() {
    Map<String, Object> copy = resolvedParams.asMap();
    assertThrows(UnsupportedOperationException.class, () -> copy.put("newKey", "newValue"));
  }

  @Test
  public void emptyParams_handlesGracefully() {
    ResolvedParams empty = new ResolvedParams(new HashMap<>());
    assertThat(empty.containsKey("any")).isFalse();
    assertThat(empty.asMap()).isEmpty();
  }

  @Test
  public void getInt_withLongValue_convertsToInt() {
    params.put("longValue", 1234567890L);
    ResolvedParams withLong = new ResolvedParams(params);
    assertThat(withLong.getInt("longValue")).isEqualTo(1234567890);
  }

  @Test
  public void getDouble_withFloatValue_convertsToDouble() {
    params.put("floatValue", 1.5f);
    ResolvedParams withFloat = new ResolvedParams(params);
    assertThat(withFloat.getDouble("floatValue")).isWithin(0.001).of(1.5);
  }
}
