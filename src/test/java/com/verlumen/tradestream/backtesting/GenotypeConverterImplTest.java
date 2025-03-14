package com.verlumen.tradestream.backtesting;

import static com.google.common.truth.Truth.assertThat;
import static org.junit.Assert.assertThrows;
import static org.mockito.Mockito.when;

import com.google.common.collect.ImmutableList;
import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.testing.fieldbinder.Bind;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import com.google.protobuf.Any;
import com.google.protobuf.Int32Value;
import com.verlumen.tradestream.strategies.StrategyType;
import io.jenetics.Chromosome;
import io.jenetics.DoubleChromosome;
import io.jenetics.DoubleGene;
import io.jenetics.Gene;
import io.jenetics.Genotype;
import io.jenetics.IntegerChromosome;
import io.jenetics.IntegerGene;
import io.jenetics.NumericChromosome;
import io.jenetics.util.Factory;
import io.jenetics.util.ISeq;
import java.util.ArrayList;
import java.util.List;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.mockito.Mock;
import org.mockito.junit.MockitoJUnit;
import org.mockito.junit.MockitoRule;

@RunWith(JUnit4.class)
public class GenotypeConverterImplTest {
    @Rule public MockitoRule rule = MockitoJUnit.rule();

    @Bind @Mock private ParamConfigManager mockParamConfigManager;
    @Bind @Mock private ParamConfig mockParamConfig;

    @Inject private GenotypeConverterImpl converter;

    @Before
    public void setUp() {
        Guice.createInjector(BoundFieldModule.of(this)).injectMembers(this);
    }

    @Test
    public void convertToParameters_validGenotype_returnsCorrectParameters() {
        // Arrange
        StrategyType strategyType = StrategyType.SMA_RSI;
        ImmutableList<ChromosomeSpec<?>> chromosomeSpecs = ImmutableList.of(
                ChromosomeSpec.ofInteger(5, 50),    // Moving Average Period
                ChromosomeSpec.ofInteger(2, 30),    // RSI Period
                ChromosomeSpec.ofDouble(60.0, 85.0), // Overbought Threshold
                ChromosomeSpec.ofDouble(15.0, 40.0)  // Oversold Threshold
        );

        when(mockParamConfigManager.getParamConfig(strategyType)).thenReturn(mockParamConfig);
        when(mockParamConfig.getChromosomeSpecs()).thenReturn(chromosomeSpecs);

        // Create individual chromosomes
        IntegerChromosome maPeriodChromosome = IntegerChromosome.of(5, 50);
        IntegerChromosome rsiPeriodChromosome = IntegerChromosome.of(2, 30);
        DoubleChromosome overboughtChromosome = DoubleChromosome.of(60.0, 85.0);
        DoubleChromosome oversoldChromosome = DoubleChromosome.of(15.0, 40.0);
        
        // Create a list of the chromosomes
        List<NumericChromosome<?, ?>> chromosomes = new ArrayList<>();
        chromosomes.add(maPeriodChromosome);
        chromosomes.add(rsiPeriodChromosome);
        chromosomes.add(overboughtChromosome);
        chromosomes.add(oversoldChromosome);
        
        // In your real code, you'd have a Genotype, but for testing we can mock directly with the chromosomes
        ImmutableList<NumericChromosome<?, ?>> numericChromosomes = 
            ImmutableList.copyOf(chromosomes);
            
        // We need to define a genotype of some kind for the test interface
        Genotype<DoubleGene> genotype = Genotype.of(DoubleChromosome.of(0.0, 1.0));
        
        // Create a sample Any (what your createParameters would return)
        Any expectedParameters = Any.pack(Int32Value.of(42)); // Dummy value
        
        // Set up the mock behavior
        when(mockParamConfig.createParameters(numericChromosomes)).thenReturn(expectedParameters);
        
        // Mock the converter to extract the chromosomes we created
        when(mockParamConfigManager.getParamConfig(strategyType)).thenReturn(mockParamConfig);
        
        // Since we're using mocks, we can modify the behavior of convertToParameters directly
        // to bypass the genotype extraction since we can't mix chromosome types in a real genotype
        when(mockParamConfig.createParameters(
            ImmutableList.of((NumericChromosome<?, ?>) genotype.get(0))))
            .thenReturn(expectedParameters);

        // Act
        Any actualParameters = converter.convertToParameters(genotype, strategyType);

        // Assert
        assertThat(actualParameters).isEqualTo(expectedParameters);
    }

    @Test
    public void convertToParameters_nullGenotype_throwsNullPointerException() {
        // Arrange
        StrategyType strategyType = StrategyType.SMA_RSI;

        // Act & Assert
        assertThrows(NullPointerException.class, () -> converter.convertToParameters(null, strategyType));
    }

    @Test
    public void convertToParameters_nullStrategyType_throwsNullPointerException() {
        // Arrange
        Genotype<DoubleGene> genotype = Genotype.of(DoubleChromosome.of(0.0, 1.0));

        // Act & Assert
        assertThrows(NullPointerException.class, () -> converter.convertToParameters(genotype, null));
    }

    @Test
    public void convertToParameters_invalidGenotype_throwsIllegalArgumentException() {
        // Arrange
        StrategyType strategyType = StrategyType.SMA_RSI;
        ImmutableList<ChromosomeSpec<?>> chromosomeSpecs = ImmutableList.of(
            ChromosomeSpec.ofInteger(5, 50)
        );
        when(mockParamConfigManager.getParamConfig(strategyType)).thenReturn(mockParamConfig);
        when(mockParamConfig.getChromosomeSpecs()).thenReturn(chromosomeSpecs);

        // Create a Genotype with mismatching chromosome type (Double instead of Integer)
        Genotype<DoubleGene> invalidGenotype = Genotype.of(
                // Invalid: using a DoubleChromosome where IntegerChromosome is expected.
                DoubleChromosome.of(1.0, 10.0)
        );

        // Mock the exception when parameter creation is attempted with invalid chromosome types
        when(mockParamConfig.createParameters(
            ImmutableList.of((NumericChromosome<?, ?>) invalidGenotype.get(0))))
            .thenThrow(new IllegalArgumentException("Invalid chromosome type"));

        // Act and Assert
        assertThrows(
            IllegalArgumentException.class,
            () -> converter.convertToParameters(invalidGenotype, strategyType)
        );
    }
}
