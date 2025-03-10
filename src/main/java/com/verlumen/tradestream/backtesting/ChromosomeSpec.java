package com.verlumen.tradestream.backtesting;

import com.google.common.collect.Range;
import io.jenetics.NumericChromosome;
import io.jenetics.NumericGene;

/**
 * Specifies type and range constraints for a chromosome in parameter optimization.
 * @param <T> The type of value being optimized (e.g. Integer, Double)
 */
public interface ChromosomeSpec<T extends Number & Comparable<? super T>> {
    /**
     * Gets the valid range for this parameter.
     */
    Range<T> getRange();

    /**
     * Creates an initial chromosome according to this specification.
     */
    NumericChromosome<T, ?> createChromosome();

    /**
     * Creates an integer-valued parameter specification.
     */
    static ChromosomeSpec<Integer> ofInteger(int min, int max) {
        return new IntegerChromosomeSpec(Range.closed(min, max));
    }

    /**
     * Creates a double-valued parameter specification.
     */
    static ChromosomeSpec<Double> ofDouble(double min, double max) {
        return new DoubleChromosomeSpec(Range.closed(min, max));
    }
}
