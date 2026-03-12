package com.verlumen.tradestream.marketregime;

import static com.google.common.base.Preconditions.checkNotNull;

/** Represents a detected regime transition between two consecutive classifications. */
public final class RegimeChangeEvent {
  private final RegimeClassification previousRegime;
  private final RegimeClassification currentRegime;
  private final int barIndex;

  public RegimeChangeEvent(
      RegimeClassification previousRegime, RegimeClassification currentRegime, int barIndex) {
    this.previousRegime = checkNotNull(previousRegime, "previousRegime");
    this.currentRegime = checkNotNull(currentRegime, "currentRegime");
    this.barIndex = barIndex;
  }

  public RegimeClassification getPreviousRegime() {
    return previousRegime;
  }

  public RegimeClassification getCurrentRegime() {
    return currentRegime;
  }

  public int getBarIndex() {
    return barIndex;
  }

  @Override
  public String toString() {
    return String.format(
        "RegimeChangeEvent{from=%s(%.2f) to=%s(%.2f) at bar %d}",
        previousRegime.getRegime(),
        previousRegime.getConfidence(),
        currentRegime.getRegime(),
        currentRegime.getConfidence(),
        barIndex);
  }
}
