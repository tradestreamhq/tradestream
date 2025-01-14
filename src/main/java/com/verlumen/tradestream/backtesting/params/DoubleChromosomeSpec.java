package com.verlumen.tradestream.backtesting.params;

import com.google.common.collect.Range;
import io.jenetics.DoubleChromosome;
import io.jenetics.NumericChromosome;

/**
 * Specification for double-valued chromosomes.
 */
final class DoubleChromosomeSpec implements ChromosomeSpec<Double> {
    private final Range<Double> range;

    DoubleChromosomeSpec(Range<Double> range) {
        this.range = range;
    }

    @Override
    public Range<Double> getRange() {
        return range;
    }

    @Override
    public NumericChromosome<Double, ?> createChromosome() {
        return DoubleChromosome.of(
            range.lowerEndpoint(),
            range.upperEndpoint());
    }
}
