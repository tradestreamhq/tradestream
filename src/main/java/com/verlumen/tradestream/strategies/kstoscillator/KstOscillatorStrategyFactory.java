package com.verlumen.tradestream.strategies.kstoscillator;

import static com.google.common.base.Preconditions.checkArgument;

import com.verlumen.tradestream.strategies.KstOscillatorParameters;
import com.verlumen.tradestream.strategies.StrategyFactory;
import com.verlumen.tradestream.strategies.StrategyType;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseStrategy;
import org.ta4j.core.Rule;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.CachedIndicator;
import org.ta4j.core.indicators.SMAIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.rules.CrossedDownIndicatorRule;
import org.ta4j.core.rules.CrossedUpIndicatorRule;

/**
 * Factory for creating KST Oscillator strategies.
 *
 * <p>The KST Oscillator combines four Rate of Change (ROC) indicators with different periods and
 * smoothing to create a comprehensive momentum indicator. The strategy generates buy signals when
 * the KST crosses above its signal line and sell signals when it crosses below.
 */
public final class KstOscillatorStrategyFactory
    implements StrategyFactory<KstOscillatorParameters> {

  @Override
  public Strategy createStrategy(BarSeries barSeries, KstOscillatorParameters parameters) {
    checkArgument(parameters.getRma1Period() > 0, "RMA1 period must be positive");
    checkArgument(parameters.getRma2Period() > 0, "RMA2 period must be positive");
    checkArgument(parameters.getRma3Period() > 0, "RMA3 period must be positive");
    checkArgument(parameters.getRma4Period() > 0, "RMA4 period must be positive");
    checkArgument(parameters.getSignalPeriod() > 0, "Signal period must be positive");

    // Create the KST Oscillator indicator
    KstOscillatorIndicator kstIndicator =
        new KstOscillatorIndicator(
            barSeries,
            parameters.getRma1Period(),
            parameters.getRma2Period(),
            parameters.getRma3Period(),
            parameters.getRma4Period());

    // Create the signal line (SMA of KST)
    SMAIndicator signalLine = new SMAIndicator(kstIndicator, parameters.getSignalPeriod());

    // Entry rule: KST crosses above signal line
    Rule entryRule = new CrossedUpIndicatorRule(kstIndicator, signalLine);

    // Exit rule: KST crosses below signal line
    Rule exitRule = new CrossedDownIndicatorRule(kstIndicator, signalLine);

    String strategyName =
        String.format(
            "%s (RMA1-%d RMA2-%d RMA3-%d RMA4-%d Signal-%d)",
            StrategyType.KST_OSCILLATOR.name(),
            parameters.getRma1Period(),
            parameters.getRma2Period(),
            parameters.getRma3Period(),
            parameters.getRma4Period(),
            parameters.getSignalPeriod());

    return new BaseStrategy(strategyName, entryRule, exitRule, parameters.getSignalPeriod());
  }

  @Override
  public KstOscillatorParameters getDefaultParameters() {
    return KstOscillatorParameters.newBuilder()
        .setRma1Period(10)
        .setRma2Period(15)
        .setRma3Period(20)
        .setRma4Period(30)
        .setSignalPeriod(9)
        .build();
  }

  /**
   * Custom KST Oscillator indicator implementation.
   *
   * <p>The KST Oscillator is calculated as: 1. Calculate ROC for four different periods (typically
   * 10, 15, 20, 30) 2. Apply SMA smoothing to each ROC (typically 10, 10, 10, 15) 3. Weight the
   * smoothed ROCs: (ROC1 * 1) + (ROC2 * 2) + (ROC3 * 3) + (ROC4 * 4) 4. KST = Weighted sum of
   * smoothed ROCs
   */
  private static class KstOscillatorIndicator extends CachedIndicator<org.ta4j.core.num.Num> {
    private final RocIndicator roc1;
    private final RocIndicator roc2;
    private final RocIndicator roc3;
    private final RocIndicator roc4;
    private final SMAIndicator smoothedRoc1;
    private final SMAIndicator smoothedRoc2;
    private final SMAIndicator smoothedRoc3;
    private final SMAIndicator smoothedRoc4;

    public KstOscillatorIndicator(
        BarSeries series, int rma1Period, int rma2Period, int rma3Period, int rma4Period) {
      super(series);

      // Create ROC indicators with different periods
      this.roc1 = new RocIndicator(series, 10);
      this.roc2 = new RocIndicator(series, 15);
      this.roc3 = new RocIndicator(series, 20);
      this.roc4 = new RocIndicator(series, 30);

      // Apply SMA smoothing to each ROC
      this.smoothedRoc1 = new SMAIndicator(roc1, rma1Period);
      this.smoothedRoc2 = new SMAIndicator(roc2, rma2Period);
      this.smoothedRoc3 = new SMAIndicator(roc3, rma3Period);
      this.smoothedRoc4 = new SMAIndicator(roc4, rma4Period);
    }

    @Override
    protected org.ta4j.core.num.Num calculate(int index) {
      // Weighted sum: (ROC1 * 1) + (ROC2 * 2) + (ROC3 * 3) + (ROC4 * 4)
      org.ta4j.core.num.Num weightedSum =
          smoothedRoc1
              .getValue(index)
              .multipliedBy(numOf(1))
              .plus(smoothedRoc2.getValue(index).multipliedBy(numOf(2)))
              .plus(smoothedRoc3.getValue(index).multipliedBy(numOf(3)))
              .plus(smoothedRoc4.getValue(index).multipliedBy(numOf(4)));

      return weightedSum;
    }

    @Override
    public int getUnstableBars() {
      // Return the maximum period needed for all components
      return Math.max(
          Math.max(
              Math.max(roc1.getUnstableBars(), roc2.getUnstableBars()),
              Math.max(roc3.getUnstableBars(), roc4.getUnstableBars())),
          Math.max(
              Math.max(smoothedRoc1.getUnstableBars(), smoothedRoc2.getUnstableBars()),
              Math.max(smoothedRoc3.getUnstableBars(), smoothedRoc4.getUnstableBars())));
    }
  }

  /**
   * Rate of Change (ROC) indicator implementation.
   *
   * <p>ROC = ((Current Price - Price n periods ago) / Price n periods ago) * 100
   */
  private static class RocIndicator extends CachedIndicator<org.ta4j.core.num.Num> {
    private final ClosePriceIndicator closePrice;
    private final int period;

    public RocIndicator(BarSeries series, int period) {
      super(series);
      this.closePrice = new ClosePriceIndicator(series);
      this.period = period;
    }

    @Override
    protected org.ta4j.core.num.Num calculate(int index) {
      if (index < period) {
        return numOf(0);
      }

      org.ta4j.core.num.Num currentPrice = closePrice.getValue(index);
      org.ta4j.core.num.Num pastPrice = closePrice.getValue(index - period);

      if (pastPrice.isZero()) {
        return numOf(0);
      }

      return currentPrice.minus(pastPrice).dividedBy(pastPrice).multipliedBy(numOf(100));
    }

    @Override
    public int getUnstableBars() {
      return period;
    }
  }
}
