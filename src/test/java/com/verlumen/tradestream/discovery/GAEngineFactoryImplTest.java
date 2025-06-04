package com.verlumen.tradestream.discovery;

import static com.google.common.truth.Truth.assertThat;
import static org.junit.Assert.assertNotNull;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;

import com.google.common.collect.ImmutableList;
import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.testing.fieldbinder.Bind;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import com.verlumen.tradestream.strategies.StrategyType;
import io.jenetics.Genotype;
import io.jenetics.engine.Engine;
import java.util.List;
import java.util.function.Function;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.mockito.Mock;
import org.mockito.junit.MockitoJUnit;
import org.mockito.junit.MockitoRule;

@RunWith(JUnit4.class)
public class GAEngineFactoryImplTest {
  @Rule public MockitoRule mockitoRule = MockitoJUnit.rule();

  @Bind @Mock private ParamConfigManager mockParamConfigManager;
  @Bind @Mock private FitnessFunctionFactory mockFitnessFunctionFactory;
  @Bind @Mock private ParamConfig mockParamConfig;

  @Inject private GAEngineFactoryImpl engineFactory;

  private StrategyDiscoveryRequest testRequest;

  @Before
  public void setUp() {
    // Setup a basic test request
    testRequest =
        StrategyDiscoveryRequest.newBuilder()
            .setStrategyType(StrategyType.SMA_RSI)
            .setGaConfig(GAConfig.newBuilder().setPopulationSize(20))
            .build();

    // Configure mocks
    when(mockParamConfigManager.getParamConfig(any(StrategyType.class)))
        .thenReturn(mockParamConfig);
    when(mockParamConfig.initialChromosomes()).thenReturn(ImmutableList.of());

    // Mock the fitness calculator to return a dummy function
    // This is critical - create should never return null
    Function<Genotype<?>, Double> dummyFunction =
        genotype -> 1.0; // Just return a constant value for testing
    when(mockFitnessFunctionFactory.create(any(StrategyType.class), any(List.class)))
        .thenReturn(dummyFunction);

    // Inject dependencies
    Guice.createInjector(BoundFieldModule.of(this)).injectMembers(this);
  }

  @Test
  public void createEngine_withValidRequest_returnsConfiguredEngine() {
    // Act
    Engine<?, Double> engine = engineFactory.createEngine(testRequest);

    // Assert
    assertNotNull("Engine should not be null", engine);
    // Verify engine configuration
    assertThat(engine).isNotNull();
  }

  @Test
  public void createEngine_withCustomPopulationSize_usesRequestedSize() {
    // Arrange
    int customSize = 42;
    StrategyDiscoveryRequest customRequest =
        testRequest.toBuilder().setGaConfig(GAConfig.newBuilder().setPopulationSize(customSize)).build();

    // Act
    Engine<?, Double> engine = engineFactory.createEngine(customRequest);

    // Assert
    assertNotNull("Engine should not be null", engine);
    // Ideally you'd verify the population size was set correctly,
    // but this information is not easily accessible from the Engine object
  }

  @Test
  public void createEngine_withZeroPopulationSize_usesDefaultSize() {
    // Arrange
    StrategyDiscoveryRequest zeroSizeRequest = testRequest.toBuilder().setGaConfig(GAConfig.newBuilder().setPopulationSize(0)).build();

    // Act
    Engine<?, Double> engine = engineFactory.createEngine(zeroSizeRequest);

    // Assert
    assertNotNull("Engine should not be null", engine);
    // Ideally verify the default population size was used
  }

  @Test
  public void createEngine_withNoGaConfigPopulationSize_usesDefaultSize() {
    // Arrange
    StrategyDiscoveryRequest noPopSizeRequest = testRequest.toBuilder().setGaConfig(GAConfig.newBuilder().clearPopulationSize()).build();

    // Act
    Engine<?, Double> engine = engineFactory.createEngine(noPopSizeRequest);

    // Assert
    assertNotNull("Engine should not be null", engine);
    // Ideally verify the default population size was used
  }

   @Test
  public void createEngine_withNoGaConfig_usesDefaultPopulationSize() {
    // Arrange
    StrategyDiscoveryRequest noGaConfigRequest = testRequest.toBuilder().clearGaConfig().build();

    // Act
    Engine<?, Double> engine = engineFactory.createEngine(noGaConfigRequest);

    // Assert
    assertNotNull("Engine should not be null", engine);
    // Ideally verify the default population size was used
  }
}
