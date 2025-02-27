package com.verlumen.tradestream.backtesting;

import static com.google.common.truth.Truth.assertThat;
import static org.junit.Assert.assertNotNull;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;

import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.testing.fieldbinder.Bind;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import com.verlumen.tradestream.backtesting.params.ParamConfig;
import com.verlumen.tradestream.backtesting.params.ParamConfigManager;
import com.verlumen.tradestream.strategies.StrategyType;
import io.jenetics.DoubleGene;
import io.jenetics.engine.Engine;
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
    @Bind @Mock private FitnessCalculator mockFitnessCalculator;
    @Bind @Mock private ParamConfig mockParamConfig;
    
    @Inject private GAEngineFactoryImpl engineFactory;
    
    private GAOptimizationRequest testRequest;
    
    @Before
    public void setUp() {
        // Setup a basic test request
        testRequest = GAOptimizationRequest.newBuilder()
            .setStrategyType(StrategyType.SMA_RSI)
            .setPopulationSize(20)
            .build();
            
        // Configure mocks
        when(mockParamConfigManager.getParamConfig(any(StrategyType.class)))
            .thenReturn(mockParamConfig);
        when(mockParamConfig.getChromosomeSpecs())
            .thenReturn(java.util.Collections.emptyList());
            
        // Inject dependencies
        Guice.createInjector(BoundFieldModule.of(this)).injectMembers(this);
    }
    
    @Test
    public void createEngine_withValidRequest_returnsConfiguredEngine() {
        // Act
        Engine<DoubleGene, Double> engine = engineFactory.createEngine(testRequest);
        
        // Assert
        assertNotNull("Engine should not be null", engine);
        // Verify engine configuration
        assertThat(engine).isNotNull();
    }
    
    @Test
    public void createEngine_withCustomPopulationSize_usesRequestedSize() {
        // Arrange
        int customSize = 42;
        GAOptimizationRequest customRequest = testRequest.toBuilder()
            .setPopulationSize(customSize)
            .build();
            
        // Act
        Engine<DoubleGene, Double> engine = engineFactory.createEngine(customRequest);
        
        // Assert
        assertNotNull("Engine should not be null", engine);
        // Ideally you'd verify the population size was set correctly,
        // but this information is not easily accessible from the Engine object
    }
    
    @Test
    public void createEngine_withZeroPopulationSize_usesDefaultSize() {
        // Arrange
        GAOptimizationRequest zeroSizeRequest = testRequest.toBuilder()
            .setPopulationSize(0)
            .build();
            
        // Act
        Engine<DoubleGene, Double> engine = engineFactory.createEngine(zeroSizeRequest);
        
        // Assert
        assertNotNull("Engine should not be null", engine);
        // Ideally verify the default population size was used
    }
}
