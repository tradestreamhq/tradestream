package com.verlumen.tradestream.marketregime;

import static com.google.common.base.Preconditions.checkArgument;
import static com.google.common.base.Preconditions.checkNotNull;

import com.google.common.collect.ImmutableList;
import java.util.Objects;

/**
 * Immutable result of a market regime classification, including the detected regime, a confidence
 * score, and recommended strategy names.
 */
public final class RegimeClassification {
  private final MarketRegime regime;
  private final double confidence;
  private final double adxValue;
  private final double atrPercent;
  private final double bbWidthPercent;
  private final ImmutableList<String> recommendedStrategies;

  private RegimeClassification(Builder builder) {
    this.regime = checkNotNull(builder.regime, "regime");
    this.confidence = builder.confidence;
    this.adxValue = builder.adxValue;
    this.atrPercent = builder.atrPercent;
    this.bbWidthPercent = builder.bbWidthPercent;
    this.recommendedStrategies =
        checkNotNull(builder.recommendedStrategies, "recommendedStrategies");
  }

  public MarketRegime getRegime() {
    return regime;
  }

  public double getConfidence() {
    return confidence;
  }

  public double getAdxValue() {
    return adxValue;
  }

  public double getAtrPercent() {
    return atrPercent;
  }

  public double getBbWidthPercent() {
    return bbWidthPercent;
  }

  public ImmutableList<String> getRecommendedStrategies() {
    return recommendedStrategies;
  }

  @Override
  public boolean equals(Object o) {
    if (this == o) return true;
    if (!(o instanceof RegimeClassification)) return false;
    RegimeClassification that = (RegimeClassification) o;
    return Double.compare(that.confidence, confidence) == 0
        && regime == that.regime
        && recommendedStrategies.equals(that.recommendedStrategies);
  }

  @Override
  public int hashCode() {
    return Objects.hash(regime, confidence, recommendedStrategies);
  }

  @Override
  public String toString() {
    return String.format(
        "RegimeClassification{regime=%s, confidence=%.2f, adx=%.2f, atrPct=%.4f, bbWidthPct=%.4f,"
            + " strategies=%s}",
        regime, confidence, adxValue, atrPercent, bbWidthPercent, recommendedStrategies);
  }

  public static Builder builder() {
    return new Builder();
  }

  public static final class Builder {
    private MarketRegime regime;
    private double confidence;
    private double adxValue;
    private double atrPercent;
    private double bbWidthPercent;
    private ImmutableList<String> recommendedStrategies = ImmutableList.of();

    private Builder() {}

    public Builder setRegime(MarketRegime regime) {
      this.regime = regime;
      return this;
    }

    public Builder setConfidence(double confidence) {
      checkArgument(
          confidence >= 0.0 && confidence <= 1.0,
          "Confidence must be between 0.0 and 1.0, got %s",
          confidence);
      this.confidence = confidence;
      return this;
    }

    public Builder setAdxValue(double adxValue) {
      this.adxValue = adxValue;
      return this;
    }

    public Builder setAtrPercent(double atrPercent) {
      this.atrPercent = atrPercent;
      return this;
    }

    public Builder setBbWidthPercent(double bbWidthPercent) {
      this.bbWidthPercent = bbWidthPercent;
      return this;
    }

    public Builder setRecommendedStrategies(ImmutableList<String> strategies) {
      this.recommendedStrategies = strategies;
      return this;
    }

    public RegimeClassification build() {
      return new RegimeClassification(this);
    }
  }
}
