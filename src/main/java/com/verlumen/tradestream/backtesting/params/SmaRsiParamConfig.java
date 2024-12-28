package com.verlumen.tradestream.backtesting.params;

import com.google.common.collect.ImmutableList;
import com.google.common.collect.Range;
import com.google.protobuf.Any;
import io.jenetics.Chromosome;
import io.jenetics.DoubleChromosome;
import io.jenetics.DoubleGene;
import io.jenetics.Gene;
import io.jenetics.Genotype;
import io.jenetics.IntegerChromosome;
import io.jenetics.IntegerGene;
import io.jenetics.util.ISeq;
import com.verlumen.tradestream.strategies.SmaRsiParameters;
import java.util.List;

/**
 * Parameter configuration for SMA/RSI strategy optimization.
 * Uses a mixed genotype of Integer and Double genes to optimize parameters.
 */
public final class SmaRsiParamConfig implements ParamConfig<Number, Gene<?,?>> {
    // Integer parameter definitions
    private static final Range<Integer> MA_PERIOD_RANGE = Range.closed(5, 50);
    private static final Range<Integer> RSI_PERIOD_RANGE = Range.closed(2, 30);
    
    // Double parameter definitions
    private static final Range<Double> OVERBOUGHT_RANGE = Range.closed(60.0, 85.0);
    private static final Range<Double> OVERSOLD_RANGE = Range.closed(15.0, 40.0);
    
    /**
     * Gets the parameter ranges for optimization.
     */
    @Override
    public ImmutableList<Range<Number>> getChromosomes() {
        return ImmutableList.of(
            Range.closed(
                MA_PERIOD_RANGE.lowerEndpoint(),
                MA_PERIOD_RANGE.upperEndpoint()),
            Range.closed(
                RSI_PERIOD_RANGE.lowerEndpoint(),
                RSI_PERIOD_RANGE.upperEndpoint()),
            Range.closed(
                OVERBOUGHT_RANGE.lowerEndpoint(),
                OVERBOUGHT_RANGE.upperEndpoint()),
            Range.closed(
                OVERSOLD_RANGE.lowerEndpoint(),
                OVERSOLD_RANGE.upperEndpoint()));
    }

    /**
     * Creates strategy parameters from a given genotype.
     */
    @Override
    @SuppressWarnings("unchecked")
    public Any createParameters(Genotype<Gene<?, ?>> genotype) {
        List<Chromosome<Gene<?, ?>>> chromosomes = genotype.getChromosomes();
        if (chromosomes.size() != 4) {
            throw new IllegalArgumentException(
                "Genotype must have exactly 4 chromosomes (MA period, RSI period, overbought, oversold)");
        }

        // Extract integer parameters
        IntegerChromosome maPeriodChrom = (IntegerChromosome) chromosomes.get(0);
        IntegerChromosome rsiPeriodChrom = (IntegerChromosome) chromosomes.get(1);
        
        // Extract double parameters
        DoubleChromosome overboughtChrom = (DoubleChromosome) chromosomes.get(2);
        DoubleChromosome oversoldChrom = (DoubleChromosome) chromosomes.get(3);

        // Build parameters
        SmaRsiParameters parameters = SmaRsiParameters.newBuilder()
            .setMovingAveragePeriod(maPeriodChrom.getGene().intValue())
            .setRsiPeriod(rsiPeriodChrom.getGene().intValue())
            .setOverboughtThreshold(overboughtChrom.getGene().doubleValue())
            .setOversoldThreshold(oversoldChrom.getGene().doubleValue())
            .build();

        return Any.pack(parameters);
    }

    /**
     * Creates the initial genotype with appropriate chromosomes for each parameter type.
     */
    @Override
    @SuppressWarnings("unchecked")
    public Genotype<Gene<?, ?>> initialGenotype() {
        // Create integer-valued chromosomes
        IntegerChromosome maPeriodChrom = IntegerChromosome.of(
            MA_PERIOD_RANGE.lowerEndpoint(),
            MA_PERIOD_RANGE.upperEndpoint());
        
        IntegerChromosome rsiPeriodChrom = IntegerChromosome.of(
            RSI_PERIOD_RANGE.lowerEndpoint(),
            RSI_PERIOD_RANGE.upperEndpoint());
        
        // Create double-valued chromosomes
        DoubleChromosome overboughtChrom = DoubleChromosome.of(
            OVERBOUGHT_RANGE.lowerEndpoint(),
            OVERBOUGHT_RANGE.upperEndpoint());
        
        DoubleChromosome oversoldChrom = DoubleChromosome.of(
            OVERSOLD_RANGE.lowerEndpoint(),
            OVERSOLD_RANGE.upperEndpoint());

        // Combine into a mixed genotype
        ISeq<Chromosome<Gene<?, ?>>> chromosomes = ISeq.of(
            (Chromosome<Gene<?, ?>>) maPeriodChrom,
            (Chromosome<Gene<?, ?>>) rsiPeriodChrom,
            (Chromosome<Gene<?, ?>>) overboughtChrom,
            (Chromosome<Gene<?, ?>>) oversoldChrom);

        return Genotype.of(chromosomes);
    }
}
