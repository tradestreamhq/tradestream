package com.verlumen.tradestream.strategies.trixsignalline;

import com.verlumen.tradestream.strategies.StrategyFactory;
import com.verlumen.tradestream.strategies.TrixSignalLineParameters;
import com.verlumen.tradestream.ta4j.TRIXIndicator;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseStrategy;
import org.ta4j.core.Rule;
import org.ta4j.core.indicators.SMAIndicator;
import org.ta4j.core.rules.CrossedDownIndicatorRule;
import org.ta4j.core.rules.CrossedUpIndicatorRule;

/**
 * Factory for creating TRIX Signal Line trading strategies.
 *
 * <p>This strategy uses the TRIX indicator and its signal line (SMA of TRIX). Entry: Buy when TRIX
 * crosses above its Signal Line Exit: Sell when TRIX crosses below its Signal Line
 */
public final class TrixSignalLineStrategyFactory
    implements StrategyFactory<TrixSignalLineParameters> {

  @Override
  public TrixSignalLineParameters getDefaultParameters() {
    return TrixSignalLineParameters.newBuilder().setTrixPeriod(15).setSignalPeriod(9).build();
  }

  @Override
  public org.ta4j.core.Strategy createStrategy(
      BarSeries series, TrixSignalLineParameters parameters) {
    // Create TRIX indicator
    TRIXIndicator trix = new TRIXIndicator(series, parameters.getTrixPeriod());

    // Create signal line (SMA of TRIX)
    SMAIndicator signalLine = new SMAIndicator(trix, parameters.getSignalPeriod());

    // Entry rule: TRIX crosses above signal line
    Rule entryRule = new CrossedUpIndicatorRule(trix, signalLine);

    // Exit rule: TRIX crosses below signal line
    Rule exitRule = new CrossedDownIndicatorRule(trix, signalLine);

    return new BaseStrategy("TRIX_SIGNAL_LINE", entryRule, exitRule);
  }
}
