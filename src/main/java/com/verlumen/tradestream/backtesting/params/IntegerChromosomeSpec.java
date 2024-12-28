package com.verlumen.tradestream.backtesting.params;

import com.google.common.collect.Range;
import io.jenetics.Chromosome;
import io.jenetics.IntegerChromosome;
import io.jenetics.IntegerGene;
import io.jenetics.Gene;

/**
 * Specification for integer-valued chromosomes.
 */
public final class IntegerChromosomeSpec implements ChromosomeSpec<Integer> {
    private final Range<Integer> range;

    IntegerChromosomeSpec(Range<Integer> range) {
        this.range = range;
    }

    @Override
    public Range<Integer> getRange() {
        return range;
    }

    @Override
    public Chromosome<IntegerGene> createChromosome() {
        return IntegerChromosome.of(
            range.lowerEndpoint(),
            range.upperEndpoint());
    }
}
