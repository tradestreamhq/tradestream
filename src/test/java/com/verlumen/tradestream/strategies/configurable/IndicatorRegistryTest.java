package com.verlumen.tradestream.strategies.configurable;

import static org.junit.Assert.*;

import java.util.Map;
import org.junit.Before;
import org.junit.Test;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBarSeriesBuilder;
import org.ta4j.core.Indicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.num.Num;

/** Tests for IndicatorRegistry verifying all indicator types can be created. */
public class IndicatorRegistryTest {

  private IndicatorRegistry registry;
  private BarSeries testSeries;
  private Indicator<Num> closePrice;

  @Before
  public void setUp() {
    registry = IndicatorRegistry.defaultRegistry();

    testSeries = new BaseBarSeriesBuilder().withName("test").build();
    for (int i = 0; i < 100; i++) {
      double price = 100 + Math.sin(i * 0.1) * 10;
      testSeries.addBar(
          java.time.ZonedDateTime.now().plusMinutes(i),
          price - 1,
          price + 2,
          price - 2,
          price,
          1000 + i);
    }

    closePrice = new ClosePriceIndicator(testSeries);
  }

  @Test
  public void testSmaIndicator() {
    ResolvedParams params = new ResolvedParams(Map.of("period", 20));
    Indicator<Num> sma = registry.create("SMA", testSeries, closePrice, params);

    assertNotNull("SMA indicator should be created", sma);
    assertNotNull("SMA should return value at bar 50", sma.getValue(50));
  }

  @Test
  public void testEmaIndicator() {
    ResolvedParams params = new ResolvedParams(Map.of("period", 20));
    Indicator<Num> ema = registry.create("EMA", testSeries, closePrice, params);

    assertNotNull("EMA indicator should be created", ema);
    assertNotNull("EMA should return value at bar 50", ema.getValue(50));
  }

  @Test
  public void testRsiIndicator() {
    ResolvedParams params = new ResolvedParams(Map.of("period", 14));
    Indicator<Num> rsi = registry.create("RSI", testSeries, closePrice, params);

    assertNotNull("RSI indicator should be created", rsi);
    Num value = rsi.getValue(50);
    assertNotNull("RSI should return value at bar 50", value);
  }

  @Test
  public void testMacdIndicator() {
    ResolvedParams params = new ResolvedParams(Map.of("shortPeriod", 12, "longPeriod", 26));
    Indicator<Num> macd = registry.create("MACD", testSeries, closePrice, params);

    assertNotNull("MACD indicator should be created", macd);
    assertNotNull("MACD should return value at bar 50", macd.getValue(50));
  }

  @Test
  public void testBollingerBands() {
    ResolvedParams params = new ResolvedParams(Map.of("period", 20, "multiplier", 2.0));

    Indicator<Num> upper = registry.create("BOLLINGER_UPPER", testSeries, closePrice, params);
    Indicator<Num> middle = registry.create("BOLLINGER_MIDDLE", testSeries, closePrice, params);
    Indicator<Num> lower = registry.create("BOLLINGER_LOWER", testSeries, closePrice, params);

    assertNotNull("Bollinger Upper should be created", upper);
    assertNotNull("Bollinger Middle should be created", middle);
    assertNotNull("Bollinger Lower should be created", lower);

    // Upper should be greater than middle, middle greater than lower
    Num upperVal = upper.getValue(50);
    Num middleVal = middle.getValue(50);
    Num lowerVal = lower.getValue(50);

    assertTrue("Upper > Middle", upperVal.isGreaterThan(middleVal));
    assertTrue("Middle > Lower", middleVal.isGreaterThan(lowerVal));
  }

  @Test
  public void testAtrIndicator() {
    ResolvedParams params = new ResolvedParams(Map.of("period", 14));
    Indicator<Num> atr = registry.create("ATR", testSeries, closePrice, params);

    assertNotNull("ATR indicator should be created", atr);
    assertNotNull("ATR should return value at bar 50", atr.getValue(50));
  }

  @Test
  public void testAdxIndicator() {
    ResolvedParams params = new ResolvedParams(Map.of("period", 14));
    Indicator<Num> adx = registry.create("ADX", testSeries, closePrice, params);

    assertNotNull("ADX indicator should be created", adx);
    assertNotNull("ADX should return value at bar 50", adx.getValue(50));
  }

  @Test
  public void testStochasticIndicators() {
    ResolvedParams params = new ResolvedParams(Map.of("period", 14, "kPeriod", 14));

    Indicator<Num> stochK = registry.create("STOCHASTIC_K", testSeries, closePrice, params);
    Indicator<Num> stochD = registry.create("STOCHASTIC_D", testSeries, closePrice, params);

    assertNotNull("Stochastic K should be created", stochK);
    assertNotNull("Stochastic D should be created", stochD);
  }

  @Test
  public void testVolumeIndicators() {
    ResolvedParams params = new ResolvedParams(Map.of("period", 20));

    Indicator<Num> obv = registry.create("OBV", testSeries, closePrice, params);
    Indicator<Num> cmf = registry.create("CMF", testSeries, closePrice, params);

    assertNotNull("OBV should be created", obv);
    assertNotNull("CMF should be created", cmf);
  }

  @Test
  public void testDonchianChannels() {
    ResolvedParams params = new ResolvedParams(Map.of("period", 20));

    Indicator<Num> upper = registry.create("DONCHIAN_UPPER", testSeries, closePrice, params);
    Indicator<Num> lower = registry.create("DONCHIAN_LOWER", testSeries, closePrice, params);
    Indicator<Num> middle = registry.create("DONCHIAN_MIDDLE", testSeries, closePrice, params);

    assertNotNull("Donchian Upper should be created", upper);
    assertNotNull("Donchian Lower should be created", lower);
    assertNotNull("Donchian Middle should be created", middle);
  }

  @Test
  public void testCaseInsensitivity() {
    ResolvedParams params = new ResolvedParams(Map.of("period", 20));

    Indicator<Num> sma1 = registry.create("SMA", testSeries, closePrice, params);
    Indicator<Num> sma2 = registry.create("sma", testSeries, closePrice, params);
    Indicator<Num> sma3 = registry.create("Sma", testSeries, closePrice, params);

    assertNotNull("Uppercase SMA should work", sma1);
    assertNotNull("Lowercase sma should work", sma2);
    assertNotNull("Mixed case Sma should work", sma3);
  }

  @Test
  public void testHasIndicator() {
    assertTrue("Registry should have SMA", registry.hasIndicator("SMA"));
    assertTrue("Registry should have EMA", registry.hasIndicator("EMA"));
    assertTrue("Registry should have RSI", registry.hasIndicator("RSI"));
    assertFalse("Registry should not have UNKNOWN", registry.hasIndicator("UNKNOWN"));
  }

  @Test(expected = IllegalArgumentException.class)
  public void testUnknownIndicator() {
    ResolvedParams params = new ResolvedParams(Map.of("period", 20));
    registry.create("UNKNOWN_INDICATOR", testSeries, closePrice, params);
  }
}
