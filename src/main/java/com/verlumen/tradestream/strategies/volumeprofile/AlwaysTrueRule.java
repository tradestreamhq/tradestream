package com.verlumen.tradestream.strategies.volumeprofile;

import org.ta4j.core.Rule;
import org.ta4j.core.TradingRecord;

public class AlwaysTrueRule implements Rule {
  @Override
  public boolean isSatisfied(int index, TradingRecord tradingRecord) {
    return true;
  }

  @Override
  public boolean isSatisfied(int index) {
    return true;
  }
}
