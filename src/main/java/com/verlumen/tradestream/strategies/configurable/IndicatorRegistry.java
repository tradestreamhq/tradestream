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
import org.ta4j.core.indicators.bollinger.BollingerBandsLowerIndicator;
import org.ta4j.core.indicators.bollinger.BollingerBandsMiddleIndicator;
import org.ta4j.core.indicators.bollinger.BollingerBandsUpperIndicator;
import org.ta4j.core.indicators.helpers.*;
import org.ta4j.core.indicators.keltner.KeltnerChannelLowerIndicator;
import org.ta4j.core.indicators.keltner.KeltnerChannelMiddleIndicator;
import org.ta4j.core.indicators.keltner.KeltnerChannelUpperIndicator;
import org.ta4j.core.indicators.statistics.StandardDeviationIndicator;
import org.ta4j.core.indicators.volume.*;
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
              series.numOf(params.getDouble("multiplier", 2.0)));
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
              series.numOf(params.getDouble("multiplier", 2.0)));
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
            new ConstantIndicator<>(series, series.numOf(params.getDouble("value"))));

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
}
