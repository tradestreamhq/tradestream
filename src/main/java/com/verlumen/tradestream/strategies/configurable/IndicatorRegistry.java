package com.verlumen.tradestream.strategies.configurable;

import java.util.HashMap;
import java.util.Map;
import org.ta4j.core.BarSeries;
import org.ta4j.core.Indicator;
import org.ta4j.core.indicators.*;
import org.ta4j.core.indicators.adx.ADXIndicator;
import org.ta4j.core.indicators.adx.MinusDIIndicator;
import org.ta4j.core.indicators.adx.PlusDIIndicator;
import org.ta4j.core.indicators.aroon.AroonDownIndicator;
import org.ta4j.core.indicators.aroon.AroonUpIndicator;
import org.ta4j.core.indicators.averages.*;
import org.ta4j.core.indicators.bollinger.BollingerBandsLowerIndicator;
import org.ta4j.core.indicators.bollinger.BollingerBandsMiddleIndicator;
import org.ta4j.core.indicators.bollinger.BollingerBandsUpperIndicator;
import org.ta4j.core.indicators.helpers.*;
import org.ta4j.core.indicators.keltner.KeltnerChannelLowerIndicator;
import org.ta4j.core.indicators.keltner.KeltnerChannelMiddleIndicator;
import org.ta4j.core.indicators.keltner.KeltnerChannelUpperIndicator;
import org.ta4j.core.indicators.statistics.StandardDeviationIndicator;
import org.ta4j.core.indicators.volume.*;
import org.ta4j.core.num.DecimalNum;
import org.ta4j.core.num.Num;

/**
 * Registry of indicator factories, mapping type names to Ta4j indicator constructors. Supports all
 * common Ta4j indicators used in trading strategies.
 */
public final class IndicatorRegistry {
  private final Map<String, IndicatorFactory> factories = new HashMap<>();

  private IndicatorRegistry() {}

  public static IndicatorRegistry defaultRegistry() {
    IndicatorRegistry registry = new IndicatorRegistry();

    // Moving Averages
    registry.register(
        "SMA", (series, input, params) -> new SMAIndicator(input, params.getInt("period")));

    registry.register(
        "EMA", (series, input, params) -> new EMAIndicator(input, params.getInt("period")));

    registry.register(
        "DEMA", (series, input, params) -> new DoubleEMAIndicator(input, params.getInt("period")));

    registry.register(
        "TEMA", (series, input, params) -> new TripleEMAIndicator(input, params.getInt("period")));

    registry.register(
        "WMA", (series, input, params) -> new WMAIndicator(input, params.getInt("period")));

    registry.register(
        "KAMA",
        (series, input, params) ->
            new KAMAIndicator(
                input,
                params.getInt("period"),
                params.getInt("fastPeriod", 2),
                params.getInt("slowPeriod", 30)));

    registry.register(
        "ZLEMA", (series, input, params) -> new ZLEMAIndicator(input, params.getInt("period")));

    // Oscillators
    registry.register(
        "RSI", (series, input, params) -> new RSIIndicator(input, params.getInt("period")));

    registry.register(
        "MACD",
        (series, input, params) ->
            new MACDIndicator(
                input, params.getInt("shortPeriod", 12), params.getInt("longPeriod", 26)));

    registry.register(
        "STOCHASTIC_K",
        (series, input, params) ->
            new StochasticOscillatorKIndicator(series, params.getInt("period")));

    registry.register(
        "STOCHASTIC_D",
        (series, input, params) ->
            new StochasticOscillatorDIndicator(
                new StochasticOscillatorKIndicator(series, params.getInt("kPeriod", 14))));

    registry.register(
        "CCI", (series, input, params) -> new CCIIndicator(series, params.getInt("period")));

    registry.register(
        "CMO", (series, input, params) -> new CMOIndicator(input, params.getInt("period")));

    // MFI - Money Flow Index (using CMF as alternative since Ta4j doesn't have MFI)
    registry.register(
        "MFI",
        (series, input, params) -> new ChaikinMoneyFlowIndicator(series, params.getInt("period")));

    registry.register(
        "WILLIAMS_R",
        (series, input, params) -> new WilliamsRIndicator(series, params.getInt("period")));

    registry.register(
        "ROC", (series, input, params) -> new ROCIndicator(input, params.getInt("period")));

    registry.register(
        "MOMENTUM", (series, input, params) -> new ROCIndicator(input, params.getInt("period")));

    registry.register(
        "TRIX", (series, input, params) -> new TripleEMAIndicator(input, params.getInt("period")));

    registry.register(
        "DPO", (series, input, params) -> new DPOIndicator(input, params.getInt("period")));

    registry.register(
        "AWESOME_OSCILLATOR",
        (series, input, params) ->
            new AwesomeOscillatorIndicator(
                new MedianPriceIndicator(series),
                params.getInt("shortPeriod", 5),
                params.getInt("longPeriod", 34)));

    // Trend Indicators
    registry.register(
        "ADX", (series, input, params) -> new ADXIndicator(series, params.getInt("period")));

    registry.register(
        "PLUS_DI", (series, input, params) -> new PlusDIIndicator(series, params.getInt("period")));

    registry.register(
        "MINUS_DI",
        (series, input, params) -> new MinusDIIndicator(series, params.getInt("period")));

    registry.register(
        "AROON_UP",
        (series, input, params) -> new AroonUpIndicator(series, params.getInt("period")));

    registry.register(
        "AROON_DOWN",
        (series, input, params) -> new AroonDownIndicator(series, params.getInt("period")));

    registry.register(
        "PARABOLIC_SAR", (series, input, params) -> new ParabolicSarIndicator(series));

    // Volatility Indicators
    registry.register(
        "ATR", (series, input, params) -> new ATRIndicator(series, params.getInt("period")));

    registry.register(
        "BOLLINGER_UPPER",
        (series, input, params) -> {
          SMAIndicator sma = new SMAIndicator(input, params.getInt("period"));
          StandardDeviationIndicator stdDev =
              new StandardDeviationIndicator(input, params.getInt("period"));
          return new BollingerBandsUpperIndicator(
              new BollingerBandsMiddleIndicator(sma),
              stdDev,
              series.numFactory().numOf(params.getDouble("multiplier", 2.0)));
        });

    registry.register(
        "BOLLINGER_MIDDLE",
        (series, input, params) ->
            new BollingerBandsMiddleIndicator(new SMAIndicator(input, params.getInt("period"))));

    registry.register(
        "BOLLINGER_LOWER",
        (series, input, params) -> {
          SMAIndicator sma = new SMAIndicator(input, params.getInt("period"));
          StandardDeviationIndicator stdDev =
              new StandardDeviationIndicator(input, params.getInt("period"));
          return new BollingerBandsLowerIndicator(
              new BollingerBandsMiddleIndicator(sma),
              stdDev,
              series.numFactory().numOf(params.getDouble("multiplier", 2.0)));
        });

    registry.register(
        "KELTNER_UPPER",
        (series, input, params) -> {
          KeltnerChannelMiddleIndicator middle =
              new KeltnerChannelMiddleIndicator(series, params.getInt("period"));
          ATRIndicator atr = new ATRIndicator(series, params.getInt("atrPeriod", 10));
          return new KeltnerChannelUpperIndicator(middle, atr, params.getDouble("multiplier", 2.0));
        });

    registry.register(
        "KELTNER_MIDDLE",
        (series, input, params) ->
            new KeltnerChannelMiddleIndicator(series, params.getInt("period")));

    registry.register(
        "KELTNER_LOWER",
        (series, input, params) -> {
          KeltnerChannelMiddleIndicator middle =
              new KeltnerChannelMiddleIndicator(series, params.getInt("period"));
          ATRIndicator atr = new ATRIndicator(series, params.getInt("atrPeriod", 10));
          return new KeltnerChannelLowerIndicator(middle, atr, params.getDouble("multiplier", 2.0));
        });

    // Donchian Channel using Highest/Lowest Value indicators
    registry.register(
        "DONCHIAN_UPPER",
        (series, input, params) ->
            new HighestValueIndicator(new HighPriceIndicator(series), params.getInt("period")));

    registry.register(
        "DONCHIAN_LOWER",
        (series, input, params) ->
            new LowestValueIndicator(new LowPriceIndicator(series), params.getInt("period")));

    registry.register(
        "DONCHIAN_MIDDLE",
        (series, input, params) -> {
          // Donchian middle is the midpoint between upper and lower channels
          // Using SMA as an approximation for the middle
          return new SMAIndicator(new ClosePriceIndicator(series), params.getInt("period"));
        });

    // Volume Indicators
    registry.register("OBV", (series, input, params) -> new OnBalanceVolumeIndicator(series));

    registry.register(
        "CMF",
        (series, input, params) -> new ChaikinMoneyFlowIndicator(series, params.getInt("period")));

    registry.register(
        "AD", (series, input, params) -> new AccumulationDistributionIndicator(series));

    registry.register(
        "CHAIKIN_OSCILLATOR",
        (series, input, params) ->
            new ChaikinOscillatorIndicator(
                series, params.getInt("shortPeriod", 3), params.getInt("longPeriod", 10)));

    registry.register("PVT", (series, input, params) -> new PVIIndicator(series));

    registry.register("NVI", (series, input, params) -> new NVIIndicator(series));

    registry.register(
        "VWAP", (series, input, params) -> new VWAPIndicator(series, params.getInt("period")));

    // Price Helpers
    registry.register("CLOSE", (series, input, params) -> new ClosePriceIndicator(series));

    registry.register("HIGH", (series, input, params) -> new HighPriceIndicator(series));

    registry.register("LOW", (series, input, params) -> new LowPriceIndicator(series));

    registry.register("OPEN", (series, input, params) -> new OpenPriceIndicator(series));

    registry.register("VOLUME", (series, input, params) -> new VolumeIndicator(series));

    registry.register(
        "TYPICAL_PRICE", (series, input, params) -> new TypicalPriceIndicator(series));

    registry.register("MEDIAN_PRICE", (series, input, params) -> new MedianPriceIndicator(series));

    // Klinger Volume Oscillator
    registry.register(
        "KLINGER_VOLUME_OSCILLATOR",
        (series, input, params) ->
            new KlingerVolumeOscillatorIndicator(
                series, params.getInt("shortPeriod", 10), params.getInt("longPeriod", 35)));

    // Mass Index
    registry.register(
        "MASS_INDEX",
        (series, input, params) ->
            new MassIndexIndicator(
                series, params.getInt("emaPeriod", 9), params.getInt("sumPeriod", 25)));

    // Statistical
    registry.register(
        "STD_DEV",
        (series, input, params) -> new StandardDeviationIndicator(input, params.getInt("period")));

    // Previous value indicator (for comparing with past values)
    registry.register(
        "PREVIOUS",
        (series, input, params) -> new PreviousValueIndicator(input, params.getInt("n", 1)));

    // Constant value indicator
    registry.register(
        "CONSTANT",
        (series, input, params) ->
            new ConstantIndicator<>(series, series.numFactory().numOf(params.getDouble("value"))));

    // Fractal Adaptive Moving Average
    registry.register(
        "FRAMA",
        (series, input, params) ->
            new FramaIndicator(
                series,
                params.getDouble("sc", 0.5),
                params.getInt("fc", 20),
                params.getDouble("alpha", 0.5)));

    return registry;
  }

  public void register(String type, IndicatorFactory factory) {
    factories.put(type.toUpperCase(), factory);
  }

  public Indicator<Num> create(
      String type, BarSeries barSeries, Indicator<Num> input, ResolvedParams params) {
    IndicatorFactory factory = factories.get(type.toUpperCase());
    if (factory == null) {
      throw new IllegalArgumentException("Unknown indicator type: " + type);
    }
    return factory.create(barSeries, input, params);
  }

  public boolean hasIndicator(String type) {
    return factories.containsKey(type.toUpperCase());
  }

  /** Klinger Volume Oscillator indicator implementation. */
  private static class KlingerVolumeOscillatorIndicator extends CachedIndicator<Num> {
    private final ClosePriceIndicator closePrice;
    private final HighPriceIndicator highPrice;
    private final LowPriceIndicator lowPrice;
    private final VolumeIndicator volume;
    private final int shortPeriod;
    private final int longPeriod;

    KlingerVolumeOscillatorIndicator(BarSeries series, int shortPeriod, int longPeriod) {
      super(series);
      this.closePrice = new ClosePriceIndicator(series);
      this.highPrice = new HighPriceIndicator(series);
      this.lowPrice = new LowPriceIndicator(series);
      this.volume = new VolumeIndicator(series);
      this.shortPeriod = shortPeriod;
      this.longPeriod = longPeriod;
    }

    @Override
    protected Num calculate(int index) {
      if (index < Math.max(shortPeriod, longPeriod)) {
        return getBarSeries().numFactory().numOf(0);
      }
      Num shortEma = getBarSeries().numFactory().numOf(0);
      Num longEma = getBarSeries().numFactory().numOf(0);
      double shortMult = 2.0 / (shortPeriod + 1);
      double longMult = 2.0 / (longPeriod + 1);
      for (int i = 1; i <= index; i++) {
        Num force = calculateForce(i);
        shortEma =
            force
                .multipliedBy(getBarSeries().numFactory().numOf(shortMult))
                .plus(shortEma.multipliedBy(getBarSeries().numFactory().numOf(1 - shortMult)));
        longEma =
            force
                .multipliedBy(getBarSeries().numFactory().numOf(longMult))
                .plus(longEma.multipliedBy(getBarSeries().numFactory().numOf(1 - longMult)));
      }
      return shortEma.minus(longEma);
    }

    private Num calculateForce(int index) {
      if (index < 1) {
        return getBarSeries().numFactory().numOf(0);
      }
      Num high = highPrice.getValue(index);
      Num low = lowPrice.getValue(index);
      Num range = high.minus(low);
      if (range.isZero()) {
        return getBarSeries().numFactory().numOf(0);
      }
      Num close = closePrice.getValue(index);
      Num prevClose = closePrice.getValue(index - 1);
      Num priceChange = close.minus(prevClose);
      return volume.getValue(index).multipliedBy(priceChange).dividedBy(range);
    }

    @Override
    public int getCountOfUnstableBars() {
      return Math.max(shortPeriod, longPeriod);
    }
  }

  /** Mass Index indicator implementation. */
  private static class MassIndexIndicator extends CachedIndicator<Num> {
    private final EMAIndicator ema;
    private final EMAIndicator doubleEma;
    private final int sumPeriod;

    MassIndexIndicator(BarSeries series, int emaPeriod, int sumPeriod) {
      super(series);
      HighLowRangeIndicator highLow = new HighLowRangeIndicator(series);
      this.ema = new EMAIndicator(highLow, emaPeriod);
      this.doubleEma = new EMAIndicator(ema, emaPeriod);
      this.sumPeriod = sumPeriod;
    }

    @Override
    protected Num calculate(int index) {
      if (index < sumPeriod - 1) {
        return getBarSeries().numFactory().numOf(0);
      }
      Num sum = getBarSeries().numFactory().numOf(0);
      for (int i = Math.max(0, index - sumPeriod + 1); i <= index; i++) {
        Num doubleEmaVal = doubleEma.getValue(i);
        if (!doubleEmaVal.isZero()) {
          sum = sum.plus(ema.getValue(i).dividedBy(doubleEmaVal));
        }
      }
      return sum;
    }

    @Override
    public int getCountOfUnstableBars() {
      return sumPeriod + ema.getCountOfUnstableBars() * 2;
    }
  }

  /** High-Low Range indicator. */
  private static class HighLowRangeIndicator extends CachedIndicator<Num> {
    HighLowRangeIndicator(BarSeries series) {
      super(series);
    }

    @Override
    protected Num calculate(int index) {
      org.ta4j.core.Bar bar = getBarSeries().getBar(index);
      return bar.getHighPrice().minus(bar.getLowPrice());
    }

    @Override
    public int getCountOfUnstableBars() {
      return 0;
    }
  }

  /** Fractal Adaptive Moving Average indicator. */
  private static class FramaIndicator extends CachedIndicator<Num> {
    private final double sc;
    private final int fc;
    private final double alpha;

    FramaIndicator(BarSeries series, double sc, int fc, double alpha) {
      super(series);
      this.sc = sc;
      this.fc = fc;
      this.alpha = alpha;
    }

    @Override
    protected Num calculate(int index) {
      if (index < fc) {
        return DecimalNum.valueOf(0);
      }

      if (index == fc) {
        return getBarSeries().getBar(index).getClosePrice();
      }

      double fractalDimension = calculateFractalDimension(index);
      double adaptiveAlpha = Math.pow(fractalDimension, alpha);

      double prevFramaVal = getValue(index - 1).doubleValue();
      double priceVal = getBarSeries().getBar(index).getClosePrice().doubleValue();
      double result = prevFramaVal + adaptiveAlpha * (priceVal - prevFramaVal);

      return DecimalNum.valueOf(result);
    }

    private double calculateFractalDimension(int index) {
      double high = getBarSeries().getBar(index).getHighPrice().doubleValue();
      double low = getBarSeries().getBar(index).getLowPrice().doubleValue();
      double close = getBarSeries().getBar(index).getClosePrice().doubleValue();

      double range = high - low;
      double body = Math.abs(close - (high + low) / 2);

      if (range == 0) return 1.0;

      double ratio = body / range;
      return 1.0 + ratio * sc;
    }

    @Override
    public int getCountOfUnstableBars() {
      return fc;
    }
  }
}
