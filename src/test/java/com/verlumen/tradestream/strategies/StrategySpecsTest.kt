package com.verlumen.tradestream.strategies

import com.google.testing.junit.testparameterinjector.TestParameter
import com.google.testing.junit.testparameterinjector.TestParameterInjector
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeFalse
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(TestParameterInjector::class)
class StrategySpecsTest {
    @Test
    fun `strategy type has a spec defined`(
        @TestParameter strategyType: StrategyType,
    ) {
        // Gracefully skip special, non-implementable enum values.
        // This prevents test failures for values we never intend to support.
        assumeFalse(
            "Skipping special enum value",
            strategyType == StrategyType.UNRECOGNIZED ||
                strategyType == StrategyType.STRATEGY_TYPE_UNSPECIFIED,
        )

        // The assertion that matters. This will fail for any valid strategy
        // that is missing from the `strategySpecMap`.
        assertTrue(
            "StrategySpec for '$strategyType' should be supported but was not. " +
                "Please add its entry to the 'strategySpecMap' in StrategySpecs.kt.",
            strategyType.isSupported(),
        )
    }
}
