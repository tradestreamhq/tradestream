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
interface ParamConfig<N extends Number & Comparable<N>, G extends NumericGene<N,G>> {
    ImmutableList<Range<T>> getChromosomes();
    Any createParameters(Genotype<G> genotype);
}
