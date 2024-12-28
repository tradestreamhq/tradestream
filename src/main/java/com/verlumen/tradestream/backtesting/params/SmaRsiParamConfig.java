package com.verlumen.tradestream.backtesting.params;

import com.google.common.collect.ImmutableList;
import com.google.common.collect.Range;
import com.google.protobuf.Any;
import io.jenetics.*;
import io.jenetics.IntegerGene;
import io.jenetics.DoubleGene;
import io.jenetics.chromosome.Chromosome;
import io.jenetics.chromosome.IntegerChromosome;
import io.jenetics.chromosome.DoubleChromosome;
import com.verlumen.tradestream.strategies.SmaRsiParameters;

import java.util.List;
import java.util.Objects;
import java.util.function.Function;

/**
 * Parameter configuration for SMA/RSI strategy optimization.
 * Supports both integer and double parameters by using Number as the superclass.
 */
public final class SmaRsiParamConfig implements ParamConfig<Number, NumericGene<? extends Number>> {

    /**
     * Represents the definition of a chromosome, including its range and gene type.
     */
    private static class ChromosomeDefinition {
        private final Range<? extends Number> range;
        private final Function<Range<? extends Number>, NumericGene<? extends Number>> geneFactory;

        /**
         * Constructs a ChromosomeDefinition.
         *
         * @param range       The range of values for the chromosome.
         * @param geneFactory A factory function to create genes based on the range.
         */
        public ChromosomeDefinition(
                Range<? extends Number> range,
                Function<Range<? extends Number>, NumericGene<? extends Number>> geneFactory) {
            this.range = Objects.requireNonNull(range, "Range cannot be null");
            this.geneFactory = Objects.requireNonNull(geneFactory, "Gene factory cannot be null");
        }

        public Range<? extends Number> getRange() {
            return range;
        }

        public NumericGene<? extends Number> createGene() {
            return geneFactory.apply(range);
        }
    }

    // Define the chromosome specifications: range and gene type
    private static final ImmutableList<ChromosomeDefinition> CHROMOSOME_DEFINITIONS = ImmutableList.of(
        // Moving Average Period (integer: 5-50)
        new ChromosomeDefinition(
            Range.closed(5, 50),
            range -> IntegerGene.of(range.lowerEndpoint().intValue(), range.upperEndpoint().intValue())
        ),
        // RSI Period (integer: 2-30)
        new ChromosomeDefinition(
            Range.closed(2, 30),
            range -> IntegerGene.of(range.lowerEndpoint().intValue(), range.upperEndpoint().intValue())
        ),
        // Overbought Threshold (double: 60.0-85.0)
        new ChromosomeDefinition(
            Range.closed(60.0, 85.0),
            range -> DoubleGene.of(range.lowerEndpoint().doubleValue(), range.upperEndpoint().doubleValue())
        ),
        // Oversold Threshold (double: 15.0-40.0)
        new ChromosomeDefinition(
            Range.closed(15.0, 40.0),
            range -> DoubleGene.of(range.lowerEndpoint().doubleValue(), range.upperEndpoint().doubleValue())
        )
    );

    /**
     * Retrieves the chromosome ranges for the genetic algorithm.
     *
     * @return An immutable list of number ranges representing each parameter's bounds.
     */
    @Override
    public ImmutableList<Range<Number>> getChromosomes() {
        return CHROMOSOME_DEFINITIONS.stream()
                .map(ChromosomeDefinition::getRange)
                .collect(ImmutableList.toImmutableList());
    }

    /**
     * Creates strategy parameters from a given genotype.
     *
     * @param genotype The genotype representing a set of parameters.
     * @return A protobuf Any object encapsulating the SMA/RSI parameters.
     */
    @Override
    public Any createParameters(Genotype<NumericGene<? extends Number>> genotype) {
        List<Chromosome<NumericGene<? extends Number>>> chromosomes = genotype.getChromosomes().asList();

        // Ensure the genotype has the expected number of chromosomes
        if (chromosomes.size() != CHROMOSOME_DEFINITIONS.size()) {
            throw new IllegalArgumentException("Genotype has an unexpected number of chromosomes.");
        }

        // Extract alleles based on chromosome definitions
        int maPeriod = extractIntegerAllele(chromosomes.get(0).gene());
        int rsiPeriod = extractIntegerAllele(chromosomes.get(1).gene());
        double overboughtThreshold = extractDoubleAllele(chromosomes.get(2).gene());
        double oversoldThreshold = extractDoubleAllele(chromosomes.get(3).gene());

        // Build the SmaRsiParameters protobuf message
        SmaRsiParameters parameters = SmaRsiParameters.newBuilder()
                .setMovingAveragePeriod(maPeriod)
                .setRsiPeriod(rsiPeriod)
                .setOverboughtThreshold(overboughtThreshold)
                .setOversoldThreshold(oversoldThreshold)
                .build();

        // Pack the parameters into a protobuf Any type
        return Any.pack(parameters);
    }

    /**
     * Extracts an integer allele from a NumericGene.
     *
     * @param gene The gene from which to extract the allele.
     * @return The integer value of the allele.
     * @throws IllegalArgumentException if the gene is not an IntegerGene.
     */
    private int extractIntegerAllele(NumericGene<? extends Number> gene) {
        if (gene instanceof IntegerGene) {
            return gene.intValue();
        } else {
            throw new IllegalArgumentException("Expected IntegerGene but found: " + gene.getClass());
        }
    }

    /**
     * Extracts a double allele from a NumericGene.
     *
     * @param gene The gene from which to extract the allele.
     * @return The double value of the allele.
     * @throws IllegalArgumentException if the gene is not a DoubleGene.
     */
    private double extractDoubleAllele(NumericGene<? extends Number> gene) {
        if (gene instanceof DoubleGene) {
            return gene.doubleValue();
        } else {
            throw new IllegalArgumentException("Expected DoubleGene but found: " + gene.getClass());
        }
    }

    /**
     * Creates an initial genotype based on the chromosome definitions, handling both integer and double genes.
     *
     * @return A Genotype representing the initial population.
     */
    public Genotype<NumericGene<? extends Number>> initialGenotype() {
        ImmutableList<Chromosome<NumericGene<? extends Number>>> chromosomes = CHROMOSOME_DEFINITIONS.stream()
                .map(ChromosomeDefinition::createGene)
                .map(gene -> {
                    if (gene instanceof IntegerGene) {
                        return (Chromosome<NumericGene<? extends Number>>) IntegerChromosome.of((IntegerGene) gene);
                    } else if (gene instanceof DoubleGene) {
                        return (Chromosome<NumericGene<? extends Number>>) DoubleChromosome.of((DoubleGene) gene);
                    } else {
                        throw new IllegalArgumentException("Unsupported gene type: " + gene.getClass());
                    }
                })
                .collect(ImmutableList.toImmutableList());

        return Genotype.of(chromosomes);
    }
}
