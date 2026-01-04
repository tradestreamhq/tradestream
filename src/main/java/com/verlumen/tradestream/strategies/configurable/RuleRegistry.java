package com.verlumen.tradestream.strategies.configurable;

import java.util.HashMap;
import java.util.Map;
import org.ta4j.core.BarSeries;
import org.ta4j.core.Indicator;
import org.ta4j.core.Rule;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.num.Num;
import org.ta4j.core.rules.*;

/**
 * Registry of rule factories, mapping condition types to Ta4j rule constructors. Supports all
 * common Ta4j rules used in trading strategies.
 */
public final class RuleRegistry {
  private final Map<String, RuleFactory> factories = new HashMap<>();

  private RuleRegistry() {}

  public static RuleRegistry defaultRegistry() {
    RuleRegistry registry = new RuleRegistry();

    // Crossover rules
    registry.register(
        "CROSSOVER",
        (series, indicators, params) -> {
          String firstId = params.getString("indicator");
          String secondId = params.getString("crosses");
          String direction = params.getString("direction", "UP");

          Indicator<Num> first = indicators.get(firstId);
          Indicator<Num> second = indicators.get(secondId);

          if (first == null) {
            throw new IllegalArgumentException("Indicator not found: " + firstId);
          }
          if (second == null) {
            throw new IllegalArgumentException("Indicator not found: " + secondId);
          }

          return direction.equalsIgnoreCase("UP")
              ? new CrossedUpIndicatorRule(first, second)
              : new CrossedDownIndicatorRule(first, second);
        });

    registry.register(
        "CROSSED_UP",
        (series, indicators, params) -> {
          String indicatorId = params.getString("indicator");
          Indicator<Num> indicator = indicators.get(indicatorId);

          if (indicator == null) {
            throw new IllegalArgumentException("Indicator not found: " + indicatorId);
          }

          if (params.containsKey("crosses")) {
            String crossesId = params.getString("crosses");
            Indicator<Num> crosses = indicators.get(crossesId);
            if (crosses == null) {
              throw new IllegalArgumentException("Indicator not found: " + crossesId);
            }
            return new CrossedUpIndicatorRule(indicator, crosses);
          } else {
            double threshold = params.getDouble("value");
            return new CrossedUpIndicatorRule(indicator, threshold);
          }
        });

    registry.register(
        "CROSSED_DOWN",
        (series, indicators, params) -> {
          String indicatorId = params.getString("indicator");
          Indicator<Num> indicator = indicators.get(indicatorId);

          if (indicator == null) {
            throw new IllegalArgumentException("Indicator not found: " + indicatorId);
          }

          if (params.containsKey("crosses")) {
            String crossesId = params.getString("crosses");
            Indicator<Num> crosses = indicators.get(crossesId);
            if (crosses == null) {
              throw new IllegalArgumentException("Indicator not found: " + crossesId);
            }
            return new CrossedDownIndicatorRule(indicator, crosses);
          } else {
            double threshold = params.getDouble("value");
            return new CrossedDownIndicatorRule(indicator, threshold);
          }
        });

    // Threshold rules
    registry.register(
        "CROSSES_ABOVE",
        (series, indicators, params) -> {
          String indicatorId = params.getString("indicator");
          Indicator<Num> indicator = indicators.get(indicatorId);

          if (indicator == null) {
            throw new IllegalArgumentException("Indicator not found: " + indicatorId);
          }

          double threshold = params.getDouble("value");
          return new CrossedUpIndicatorRule(indicator, threshold);
        });

    registry.register(
        "CROSSES_BELOW",
        (series, indicators, params) -> {
          String indicatorId = params.getString("indicator");
          Indicator<Num> indicator = indicators.get(indicatorId);

          if (indicator == null) {
            throw new IllegalArgumentException("Indicator not found: " + indicatorId);
          }

          double threshold = params.getDouble("value");
          return new CrossedDownIndicatorRule(indicator, threshold);
        });

    // Comparison rules
    registry.register(
        "ABOVE",
        (series, indicators, params) -> {
          String indicatorId = params.getString("indicator");
          Indicator<Num> indicator = indicators.get(indicatorId);

          if (indicator == null) {
            throw new IllegalArgumentException("Indicator not found: " + indicatorId);
          }

          if (params.containsKey("other")) {
            String otherId = params.getString("other");
            Indicator<Num> other = indicators.get(otherId);
            if (other == null) {
              throw new IllegalArgumentException("Indicator not found: " + otherId);
            }
            return new OverIndicatorRule(indicator, other);
          } else {
            double threshold = params.getDouble("value");
            return new OverIndicatorRule(indicator, threshold);
          }
        });

    registry.register(
        "BELOW",
        (series, indicators, params) -> {
          String indicatorId = params.getString("indicator");
          Indicator<Num> indicator = indicators.get(indicatorId);

          if (indicator == null) {
            throw new IllegalArgumentException("Indicator not found: " + indicatorId);
          }

          if (params.containsKey("other")) {
            String otherId = params.getString("other");
            Indicator<Num> other = indicators.get(otherId);
            if (other == null) {
              throw new IllegalArgumentException("Indicator not found: " + otherId);
            }
            return new UnderIndicatorRule(indicator, other);
          } else {
            double threshold = params.getDouble("value");
            return new UnderIndicatorRule(indicator, threshold);
          }
        });

    registry.register(
        "OVER",
        (series, indicators, params) -> {
          String indicatorId = params.getString("indicator");
          Indicator<Num> indicator = indicators.get(indicatorId);

          if (indicator == null) {
            throw new IllegalArgumentException("Indicator not found: " + indicatorId);
          }

          if (params.containsKey("other")) {
            String otherId = params.getString("other");
            Indicator<Num> other = indicators.get(otherId);
            if (other == null) {
              throw new IllegalArgumentException("Indicator not found: " + otherId);
            }
            return new OverIndicatorRule(indicator, other);
          } else {
            double threshold = params.getDouble("value");
            return new OverIndicatorRule(indicator, threshold);
          }
        });

    registry.register(
        "UNDER",
        (series, indicators, params) -> {
          String indicatorId = params.getString("indicator");
          Indicator<Num> indicator = indicators.get(indicatorId);

          if (indicator == null) {
            throw new IllegalArgumentException("Indicator not found: " + indicatorId);
          }

          if (params.containsKey("other")) {
            String otherId = params.getString("other");
            Indicator<Num> other = indicators.get(otherId);
            if (other == null) {
              throw new IllegalArgumentException("Indicator not found: " + otherId);
            }
            return new UnderIndicatorRule(indicator, other);
          } else {
            double threshold = params.getDouble("value");
            return new UnderIndicatorRule(indicator, threshold);
          }
        });

    // Boolean rules
    registry.register(
        "IS_RISING",
        (series, indicators, params) -> {
          String indicatorId = params.getString("indicator");
          Indicator<Num> indicator = indicators.get(indicatorId);

          if (indicator == null) {
            throw new IllegalArgumentException("Indicator not found: " + indicatorId);
          }

          int barCount = params.getInt("barCount", 1);
          return new IsRisingRule(indicator, barCount);
        });

    registry.register(
        "IS_FALLING",
        (series, indicators, params) -> {
          String indicatorId = params.getString("indicator");
          Indicator<Num> indicator = indicators.get(indicatorId);

          if (indicator == null) {
            throw new IllegalArgumentException("Indicator not found: " + indicatorId);
          }

          int barCount = params.getInt("barCount", 1);
          return new IsFallingRule(indicator, barCount);
        });

    // Boolean logic
    registry.register(
        "AND",
        (series, indicators, params) -> {
          throw new UnsupportedOperationException(
              "AND rule should be handled by combining conditions");
        });

    registry.register(
        "OR",
        (series, indicators, params) -> {
          throw new UnsupportedOperationException(
              "OR rule should be handled by combining conditions");
        });

    // Stop loss / take profit
    registry.register(
        "STOP_GAIN",
        (series, indicators, params) -> {
          double gainPercentage = params.getDouble("percentage");
          ClosePriceIndicator closePrice = new ClosePriceIndicator(series);
          return new StopGainRule(closePrice, gainPercentage);
        });

    registry.register(
        "STOP_LOSS",
        (series, indicators, params) -> {
          double lossPercentage = params.getDouble("percentage");
          ClosePriceIndicator closePrice = new ClosePriceIndicator(series);
          return new StopLossRule(closePrice, lossPercentage);
        });

    registry.register(
        "TRAILING_STOP_LOSS",
        (series, indicators, params) -> {
          double lossPercentage = params.getDouble("percentage");
          ClosePriceIndicator closePrice = new ClosePriceIndicator(series);
          return new TrailingStopLossRule(closePrice, series.numOf(lossPercentage));
        });

    return registry;
  }

  public void register(String type, RuleFactory factory) {
    factories.put(type.toUpperCase(), factory);
  }

  public Rule create(
      String type,
      BarSeries barSeries,
      Map<String, Indicator<Num>> indicators,
      ResolvedParams params) {
    RuleFactory factory = factories.get(type.toUpperCase());
    if (factory == null) {
      throw new IllegalArgumentException("Unknown rule type: " + type);
    }
    return factory.create(barSeries, indicators, params);
  }

  public boolean hasRule(String type) {
    return factories.containsKey(type.toUpperCase());
  }
}
