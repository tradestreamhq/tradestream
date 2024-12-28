package com.verlumen.tradestream.backtesting.params;

import com.google.common.collect.Range;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;

/**
 * Specification for integer-valued chromosomes.
 */
final class IntegerChromosomeSpec implements ChromosomeSpec<Integer> {
    private final Range<Integer> range;

    IntegerChromosomeSpec(Range<Integer> range) {
        this.range = range;
    }

    @Override
    public Range<Integer> getRange() {
        return range;
    }

    @Override
    public NumericChromosome<Integer, ?> createChromosome() {
        return IntegerChromosome.of(
            range.lowerEndpoint(),
            range.upperEndpoint());
    }
}
