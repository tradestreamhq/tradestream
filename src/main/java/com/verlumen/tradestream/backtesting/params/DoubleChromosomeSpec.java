package com.verlumen.tradestream.backtesting.params;

import com.google.common.collect.Range;
import io.jenetics.Chromosome;
import io.jenetics.DoubleChromosome;
import io.jenetics.DoubleGene;
import io.jenetics.Gene;

/**
 * Specification for double-valued chromosomes.
 */
public final class DoubleChromosomeSpec implements ChromosomeSpec<Double> {
    private final Range<Double> range;

    DoubleChromosomeSpec(Range<Double> range) {
        this.range = range;
    }

    @Override
    public Range<Double> getRange() {
        return range;
    }

    @Override
    public Chromosome<DoubleGene> createChromosome() {
        return DoubleChromosome.of(
            range.lowerEndpoint(),
            range.upperEndpoint());
    }
}
