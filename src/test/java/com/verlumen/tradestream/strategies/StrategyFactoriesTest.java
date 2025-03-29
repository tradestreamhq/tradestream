package com.verlumen.tradestream.strategies;

import static com.google.common.collect.MoreCollectors.onlyElement;
import static com.google.common.truth.Truth.assertThat;
import static org.junit.Assume.assumeTrue;

import com.google.testing.junit.testparameterinjector.TestParameter;
import com.google.testing.junit.testparameterinjector.TestParameterInjector;
import org.junit.Test;
import org.junit.runner.RunWith;

@RunWith(TestParameterInjector.class)
public class StrategyFactoriesTest {
    @Test
    public void testStrategyFactoryNotNullForStrategyType(@TestParameter StrategyType strategyType) {
        // Arrange: Skip this test if the strategy type is unspecified.
        assumeTrue("Skipping test for unsupported strategy type", StrategyConstants.supportedStrategyTypes.contains(strategyType));

        // Act: Find the StrategyFactory corresponding to the provided strategy type.
        StrategyFactory factoryOptional = StrategyFactories.ALL_FACTORIES.stream()
                .filter(pc -> strategyType.equals(pc.getStrategyType()))
                .collect(onlyElement());

        // Assert: Verify that the factoryuration is not null.
        assertThat(factoryOptional).isNotNull();
    }
}
