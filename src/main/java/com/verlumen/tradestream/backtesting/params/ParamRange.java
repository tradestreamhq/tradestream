package com.verlumen.tradestream.backtesting.params;

import static com.google.common.base.Preconditions.checkArgument;

import com.google.auto.value.AutoValue;

/**
 * Represents a parameter's valid range for genetic optimization.
 */
@AutoValue
abstract class ParamRange<T extends Comparable> {
    abstract T min();
    abstract T max();

    static ParamRange create(T min, T max) {
        checkArgument(min.compareTo(max) < 0);
        return new AutoValue_ParamConfig_ParamRange(min, max);
    }
}
