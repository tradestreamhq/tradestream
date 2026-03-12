package com.verlumen.tradestream.marketregime;

import static com.google.common.base.Preconditions.checkArgument;
import static com.google.common.base.Preconditions.checkNotNull;

import com.google.common.collect.ImmutableList;
import com.google.common.collect.ImmutableMap;
import java.io.Serializable;
import org.ta4j.core.BarSeries;
import org.ta4j.core.indicators.ATRIndicator;
import org.ta4j.core.indicators.adx.ADXIndicator;
import org.ta4j.core.indicators.adx.MinusDIIndicator;
import org.ta4j.core.indicators.adx.PlusDIIndicator;
import org.ta4j.core.indicators.averages.SMAIndicator;
import org.ta4j.core.indicators.bollinger.BollingerBandsLowerIndicator;
import org.ta4j.core.indicators.bollinger.BollingerBandsMiddleIndicator;
import org.ta4j.core.indicators.bollinger.BollingerBandsUpperIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.indicators.statistics.StandardDeviationIndicator;

/**
 * Classifies the current market regime by analyzing ADX (trend strength), ATR (volatility relative
 * to price), and Bollinger Band width (price compression).
 *
 * <p>Classification logic:
 *
 * <ul>
 *   <li>ADX > adxTrendThreshold => trending (direction from +DI vs -DI)
 *   <li>ADX <= adxTrendThreshold and high ATR% => high-volatility (choppy)
 *   <li>ADX <= adxTrendThreshold and low BB width => low-volatility (quiet)
 *   <li>Otherwise => ranging
 * </ul>
 */
public final class MarketRegimeDetector implements Serializable {
  private static final long serialVersionUID = 1L;

  private final int adxPeriod;
  private final int atrPeriod;
  private final int bbPeriod;
  private final double adxTrendThreshold;
  private final double highVolatilityAtrThreshold;
  private final double lowVolatilityBbWidthThreshold;

  private static final ImmutableMap<MarketRegime, ImmutableList<String>> REGIME_STRATEGIES =
      ImmutableMap.<MarketRegime, ImmutableList<String>>builder()
          .put(
              MarketRegime.TRENDING_UP,
              ImmutableList.of(
                  "ADX_DMI",
                  "MACD_CROSSOVER",
                  "EMA_MACD",
                  "PARABOLIC_SAR",
                  "TRIPLE_EMA_CROSSOVER",
                  "ICHIMOKU_CLOUD",
                  "MOMENTUM_SMA_CROSSOVER"))
          .put(
              MarketRegime.TRENDING_DOWN,
              ImmutableList.of(
                  "ADX_DMI",
                  "MACD_CROSSOVER",
                  "EMA_MACD",
                  "PARABOLIC_SAR",
                  "ATR_TRAILING_STOP",
                  "VOLATILITY_STOP"))
          .put(
              MarketRegime.RANGING,
              ImmutableList.of(
                  "BBAND_W_R",
                  "RSI_EMA_CROSSOVER",
                  "STOCHASTIC_RSI",
                  "SMA_RSI",
                  "VWAP_MEAN_REVERSION",
                  "PIVOT",
                  "FIBONACCI_RETRACEMENTS"))
          .put(
              MarketRegime.HIGH_VOLATILITY,
              ImmutableList.of(
                  "ATR_TRAILING_STOP",
                  "VOLATILITY_STOP",
                  "ATR_CCI",
                  "DONCHIAN_BREAKOUT",
                  "VOLUME_BREAKOUT",
                  "KELTNER_CHANNEL"))
          .put(
              MarketRegime.LOW_VOLATILITY,
              ImmutableList.of(
                  "BBAND_W_R",
                  "DONCHIAN_BREAKOUT",
                  "RANGE_BARS",
                  "SMA_EMA_CROSSOVER",
                  "DOUBLE_EMA_CROSSOVER"))
          .buildOrThrow();

  private MarketRegimeDetector(Builder builder) {
    this.adxPeriod = builder.adxPeriod;
    this.atrPeriod = builder.atrPeriod;
    this.bbPeriod = builder.bbPeriod;
    this.adxTrendThreshold = builder.adxTrendThreshold;
    this.highVolatilityAtrThreshold = builder.highVolatilityAtrThreshold;
    this.lowVolatilityBbWidthThreshold = builder.lowVolatilityBbWidthThreshold;
  }

  /**
   * Classifies the market regime at the given bar index.
   *
   * @param series the bar series to analyze
   * @param index the bar index at which to classify
   * @return the regime classification with confidence and recommendations
   */
  public RegimeClassification classify(BarSeries series, int index) {
    checkNotNull(series, "series");
    checkArgument(
        index >= 0 && index < series.getBarCount(),
        "index %s out of range [0, %s)",
        index,
        series.getBarCount());

    ClosePriceIndicator closePrice = new ClosePriceIndicator(series);

    // Trend strength
    ADXIndicator adx = new ADXIndicator(series, adxPeriod);
    PlusDIIndicator plusDI = new PlusDIIndicator(series, adxPeriod);
    MinusDIIndicator minusDI = new MinusDIIndicator(series, adxPeriod);

    // Volatility - ATR as percentage of price
    ATRIndicator atr = new ATRIndicator(series, atrPeriod);

    // Bollinger Band width as percentage of middle band
    SMAIndicator sma = new SMAIndicator(closePrice, bbPeriod);
    StandardDeviationIndicator stdDev = new StandardDeviationIndicator(closePrice, bbPeriod);
    BollingerBandsMiddleIndicator bbMiddle = new BollingerBandsMiddleIndicator(sma);
    BollingerBandsUpperIndicator bbUpper = new BollingerBandsUpperIndicator(bbMiddle, stdDev);
    BollingerBandsLowerIndicator bbLower = new BollingerBandsLowerIndicator(bbMiddle, stdDev);

    double adxValue = adx.getValue(index).doubleValue();
    double plusDIValue = plusDI.getValue(index).doubleValue();
    double minusDIValue = minusDI.getValue(index).doubleValue();

    double atrValue = atr.getValue(index).doubleValue();
    double closePriceValue = closePrice.getValue(index).doubleValue();
    double atrPercent = closePriceValue > 0 ? atrValue / closePriceValue : 0;

    double bbUpperValue = bbUpper.getValue(index).doubleValue();
    double bbLowerValue = bbLower.getValue(index).doubleValue();
    double bbMiddleValue = bbMiddle.getValue(index).doubleValue();
    double bbWidthPercent = bbMiddleValue > 0 ? (bbUpperValue - bbLowerValue) / bbMiddleValue : 0;

    MarketRegime regime;
    double confidence;

    if (adxValue > adxTrendThreshold) {
      // Strong trend detected
      if (plusDIValue > minusDIValue) {
        regime = MarketRegime.TRENDING_UP;
      } else {
        regime = MarketRegime.TRENDING_DOWN;
      }
      // Confidence scales with how far ADX exceeds threshold (max at ADX=50)
      confidence = Math.min(1.0, (adxValue - adxTrendThreshold) / (50.0 - adxTrendThreshold));
      // Boost confidence if DI spread is wide
      double diSpread = Math.abs(plusDIValue - minusDIValue);
      confidence = Math.min(1.0, confidence + diSpread / 100.0);
    } else if (atrPercent > highVolatilityAtrThreshold) {
      regime = MarketRegime.HIGH_VOLATILITY;
      confidence = Math.min(1.0, atrPercent / (highVolatilityAtrThreshold * 2));
    } else if (bbWidthPercent < lowVolatilityBbWidthThreshold) {
      regime = MarketRegime.LOW_VOLATILITY;
      confidence =
          Math.min(
              1.0,
              (lowVolatilityBbWidthThreshold - bbWidthPercent) / lowVolatilityBbWidthThreshold);
    } else {
      regime = MarketRegime.RANGING;
      // Confidence is higher when ADX is very low (strong range signal)
      confidence = Math.min(1.0, (adxTrendThreshold - adxValue) / adxTrendThreshold);
    }

    // Clamp confidence
    confidence = Math.max(0.0, Math.min(1.0, confidence));

    ImmutableList<String> strategies = REGIME_STRATEGIES.getOrDefault(regime, ImmutableList.of());

    return RegimeClassification.builder()
        .setRegime(regime)
        .setConfidence(confidence)
        .setAdxValue(adxValue)
        .setAtrPercent(atrPercent)
        .setBbWidthPercent(bbWidthPercent)
        .setRecommendedStrategies(strategies)
        .build();
  }

  /**
   * Detects whether a regime change occurred between two consecutive bar indices.
   *
   * @param series the bar series
   * @param previousIndex the earlier bar index
   * @param currentIndex the later bar index
   * @return a RegimeChangeEvent if the regime changed, null otherwise
   */
  public RegimeChangeEvent detectChange(BarSeries series, int previousIndex, int currentIndex) {
    checkArgument(
        previousIndex < currentIndex,
        "previousIndex %s must be less than currentIndex %s",
        previousIndex,
        currentIndex);

    RegimeClassification previous = classify(series, previousIndex);
    RegimeClassification current = classify(series, currentIndex);

    if (previous.getRegime() != current.getRegime()) {
      return new RegimeChangeEvent(previous, current, currentIndex);
    }
    return null;
  }

  public static Builder builder() {
    return new Builder();
  }

  public static MarketRegimeDetector withDefaults() {
    return builder().build();
  }

  public static final class Builder {
    private int adxPeriod = 14;
    private int atrPeriod = 14;
    private int bbPeriod = 20;
    private double adxTrendThreshold = 25.0;
    private double highVolatilityAtrThreshold = 0.03;
    private double lowVolatilityBbWidthThreshold = 0.02;

    private Builder() {}

    public Builder setAdxPeriod(int adxPeriod) {
      checkArgument(adxPeriod > 0, "adxPeriod must be positive");
      this.adxPeriod = adxPeriod;
      return this;
    }

    public Builder setAtrPeriod(int atrPeriod) {
      checkArgument(atrPeriod > 0, "atrPeriod must be positive");
      this.atrPeriod = atrPeriod;
      return this;
    }

    public Builder setBbPeriod(int bbPeriod) {
      checkArgument(bbPeriod > 0, "bbPeriod must be positive");
      this.bbPeriod = bbPeriod;
      return this;
    }

    public Builder setAdxTrendThreshold(double threshold) {
      checkArgument(threshold > 0, "adxTrendThreshold must be positive");
      this.adxTrendThreshold = threshold;
      return this;
    }

    public Builder setHighVolatilityAtrThreshold(double threshold) {
      checkArgument(threshold > 0, "highVolatilityAtrThreshold must be positive");
      this.highVolatilityAtrThreshold = threshold;
      return this;
    }

    public Builder setLowVolatilityBbWidthThreshold(double threshold) {
      checkArgument(threshold > 0, "lowVolatilityBbWidthThreshold must be positive");
      this.lowVolatilityBbWidthThreshold = threshold;
      return this;
    }

    public MarketRegimeDetector build() {
      return new MarketRegimeDetector(this);
    }
  }
}
