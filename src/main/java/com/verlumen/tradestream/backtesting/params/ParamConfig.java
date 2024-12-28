package com.verlumen.tradestream.backtesting;

import static com.google.common.base.Preconditions.checkArgument;

import com.google.auto.value.AutoValue;
import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import io.jenetics.Genotype;
import io.jenetics.DoubleGene;

/**
 * Interface for strategy-specific parameter configuration.
 * Defines parameter ranges and conversion logic.
 */
interface ParamConfig {
    ImmutableList<ParamRange> getChromosomes();
    Any createParameters(Genotype<DoubleGene> genotype);

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
}
