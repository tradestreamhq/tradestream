package com.verlumen.tradestream.backtesting;

import static com.google.common.base.Preconditions.checkArgument;

import com.google.auto.value.AutoValue;
import com.google.common.collect.ImmutableList;
import com.google.common.collect.Range;
import com.google.protobuf.Any;
import io.jenetics.Genotype;
import io.jenetics.NumericGene;

/**
 * Interface for strategy-specific parameter configuration.
 * Defines parameter ranges and conversion logic.
 */
interface ParamConfig<T extends Number & Comparable<T>> {
    ImmutableList<Range<T>> getChromosomes();
    Any createParameters(Genotype<? extends NumericGene<T>> genotype);
}
