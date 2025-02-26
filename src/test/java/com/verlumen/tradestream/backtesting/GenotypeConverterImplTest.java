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
import com.verlumen.tradestream.backtesting.params.ChromosomeSpec;
import com.verlumen.tradestream.backtesting.params.ParamConfig;
import com.verlumen.tradestream.backtesting.params.ParamConfigManager;
import com.verlumen.tradestream.strategies.StrategyType;
import io.jenetics.DoubleChromosome;
import io.jenetics.DoubleGene;
import io.jenetics.Genotype;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;
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

        // Create a sample Genotype (ensure it matches the ChromosomeSpecs)
        Genotype<DoubleGene> genotype = Genotype.of(
                IntegerChromosome.of(10, 5, 50),     // MA Period = 10
                IntegerChromosome.of(15, 2, 30),     // RSI Period = 15
                DoubleChromosome.of(70.0, 60.0, 85.0), // Overbought = 70.0
                DoubleChromosome.of(30.0, 15.0, 40.0)  // Oversold = 30.0
        );

        // Create a sample Any (what your createParameters would return)
        Any expectedParameters = Any.pack(Int32Value.of(42)); // Dummy value
        ImmutableList<NumericChromosome<?, ?>> numericChromosomes = ImmutableList.of(
                (NumericChromosome<?, ?>) genotype.get(0),
                (NumericChromosome<?, ?>) genotype.get(1),
                (NumericChromosome<?, ?>) genotype.get(2),
                (NumericChromosome<?, ?>) genotype.get(3)
        );
        when(mockParamConfig.createParameters(numericChromosomes)).thenReturn(expectedParameters);

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

        // Create a Genotype with mismatching chromosome type (String instead of Integer/Double)
        Genotype<DoubleGene> invalidGenotype = Genotype.of(
                // Invalid: using a DoubleChromosome where IntegerChromosome is expected.
                DoubleChromosome.of(1.0, 10.0)  // This is invalid
        );

        // Act and Assert
        assertThrows(
            IllegalArgumentException.class,
            () -> converter.convertToParameters(invalidGenotype, strategyType)
        );
    }
}
