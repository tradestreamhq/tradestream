package com.verlumen.tradestream.discovery;

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
import com.verlumen.tradestream.discovery.ParamConfig;
import com.verlumen.tradestream.discovery.ParamConfigManager;
import com.verlumen.tradestream.strategies.StrategyType;
import io.jenetics.DoubleChromosome;
import io.jenetics.DoubleGene;
import io.jenetics.Genotype;
import io.jenetics.NumericChromosome;
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
    when(mockParamConfigManager.getParamConfig(strategyType)).thenReturn(mockParamConfig);

    // We need to define a genotype for the test
    Genotype<DoubleGene> genotype = Genotype.of(DoubleChromosome.of(0.0, 1.0));

    // Create a sample Any (what your createParameters would return)
    Any expectedParameters = Any.pack(Int32Value.of(42)); // Dummy value

    // Mock behavior to return our expected parameters
    List<NumericChromosome<?, ?>> chromosomes = new ArrayList<>();
    chromosomes.add((DoubleChromosome) genotype.get(0));
    when(mockParamConfig.createParameters(ImmutableList.copyOf(chromosomes)))
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
    assertThrows(
        NullPointerException.class, () -> converter.convertToParameters(null, strategyType));
  }

  @Test
  public void convertToParameters_nullStrategyType_throwsNullPointerException() {
    // Arrange
    Genotype<DoubleGene> genotype = Genotype.of(DoubleChromosome.of(0.0, 1.0));

    // Act & Assert
    assertThrows(NullPointerException.class, () -> converter.convertToParameters(genotype, null));
  }

  @Test
  public void convertToParameters_invalidChromosomeType_throwsIllegalArgumentException() {
    // Arrange
    StrategyType strategyType = StrategyType.SMA_RSI;
    when(mockParamConfigManager.getParamConfig(strategyType)).thenReturn(mockParamConfig);

    // Create a Genotype with a chromosome
    Genotype<DoubleGene> genotype = Genotype.of(DoubleChromosome.of(0.0, 1.0));

    // Mock behavior to throw exception for this chromosome
    List<NumericChromosome<?, ?>> chromosomes = new ArrayList<>();
    chromosomes.add((DoubleChromosome) genotype.get(0));
    when(mockParamConfig.createParameters(ImmutableList.copyOf(chromosomes)))
        .thenThrow(new IllegalArgumentException("Invalid chromosome type"));

    // Act & Assert
    assertThrows(
        IllegalArgumentException.class,
        () -> converter.convertToParameters(genotype, strategyType));
  }
}
