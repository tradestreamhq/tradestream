package com.verlumen.tradestream.strategies.configurable;

import static org.junit.Assert.*;

import java.util.HashMap;
import java.util.Map;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;

@RunWith(JUnit4.class)
public class ResolvedParamsTest {

  private ResolvedParams params;

  @Before
  public void setUp() {
    Map<String, Object> map = new HashMap<>();
    map.put("intParam", 14);
    map.put("doubleParam", 0.5);
    map.put("stringParam", "value");
    map.put("intAsString", "42");
    map.put("doubleAsString", "3.14");
    params = new ResolvedParams(map);
  }

  @Test
  public void getInt_returnsIntValue() {
    assertEquals(14, params.getInt("intParam"));
  }

  @Test
  public void getInt_parsesStringValue() {
    assertEquals(42, params.getInt("intAsString"));
  }

  @Test(expected = IllegalArgumentException.class)
  public void getInt_missingKey_throws() {
    params.getInt("missing");
  }

  @Test
  public void getIntWithDefault_returnsValue() {
    assertEquals(14, params.getInt("intParam", 99));
  }

  @Test
  public void getIntWithDefault_returnsDefaultWhenMissing() {
    assertEquals(99, params.getInt("missing", 99));
  }

  @Test
  public void getIntWithDefault_parsesStringValue() {
    assertEquals(42, params.getInt("intAsString", 0));
  }

  @Test
  public void getDouble_returnsDoubleValue() {
    assertEquals(0.5, params.getDouble("doubleParam"), 0.001);
  }

  @Test
  public void getDouble_parsesStringValue() {
    assertEquals(3.14, params.getDouble("doubleAsString"), 0.001);
  }

  @Test(expected = IllegalArgumentException.class)
  public void getDouble_missingKey_throws() {
    params.getDouble("missing");
  }

  @Test
  public void getDoubleWithDefault_returnsValue() {
    assertEquals(0.5, params.getDouble("doubleParam", 1.0), 0.001);
  }

  @Test
  public void getDoubleWithDefault_returnsDefaultWhenMissing() {
    assertEquals(1.0, params.getDouble("missing", 1.0), 0.001);
  }

  @Test
  public void getDoubleWithDefault_parsesStringValue() {
    assertEquals(3.14, params.getDouble("doubleAsString", 0.0), 0.001);
  }

  @Test
  public void getString_returnsStringValue() {
    assertEquals("value", params.getString("stringParam"));
  }

  @Test(expected = IllegalArgumentException.class)
  public void getString_missingKey_throws() {
    params.getString("missing");
  }

  @Test
  public void getStringWithDefault_returnsValue() {
    assertEquals("value", params.getString("stringParam", "default"));
  }

  @Test
  public void getStringWithDefault_returnsDefaultWhenMissing() {
    assertEquals("default", params.getString("missing", "default"));
  }

  @Test
  public void containsKey_existingKey_returnsTrue() {
    assertTrue(params.containsKey("intParam"));
  }

  @Test
  public void containsKey_missingKey_returnsFalse() {
    assertFalse(params.containsKey("missing"));
  }

  @Test
  public void get_returnsRawValue() {
    assertEquals(14, params.get("intParam"));
  }

  @Test
  public void asMap_returnsUnmodifiableCopy() {
    Map<String, Object> map = params.asMap();
    assertEquals(5, map.size());
    assertTrue(map.containsKey("intParam"));
  }
}
