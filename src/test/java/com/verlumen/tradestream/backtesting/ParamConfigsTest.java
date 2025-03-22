package com.verlumen.tradestream.backtesting;

import static com.google.common.collect.MoreCollectors.onlyElement;
import static com.google.common.truth.Truth.assertThat;
import static org.junit.Assume.assumeTrue;

import com.google.testing.junit.testparameterinjector.TestParameter;
import com.google.testing.junit.testparameterinjector.TestParameterInjector;
import com.verlumen.tradestream.strategies.StrategyType;
import com.verlumen.tradestream.strategies.StrategyConstants;
import org.junit.Test;
import org.junit.runner.RunWith;

@RunWith(TestParameterInjector.class)
public class ParamConfigsTest {
    @Test
    public void testParamConfigNotNullForStrategyType(@TestParameter StrategyType strategyType) {
        // Arrange: Skip this test if the strategy type is unspecified.
        assumeTrue("Skipping test for unsupported strategy type", StrategyConstants.supportedStrategyTypes.contains(strategyType));

        // Act: Find the ParamConfig corresponding to the provided strategy type.
        ParamConfig configOptional = ParamConfigs.ALL_CONFIGS.stream()
                .filter(pc -> strategyType.equals(pc.getStrategyType()))
                .collect(onlyElement());

        // Assert: Verify that the configuration is not null.
        assertThat(configOptional).isNotNull();
    }
}
