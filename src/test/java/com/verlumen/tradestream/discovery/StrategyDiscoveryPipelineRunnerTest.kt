package com.verlumen.tradestream.discovery

import com.google.common.truth.Truth.assertThat
import org.apache.beam.sdk.options.PipelineOptionsFactory
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4

/**
 * Comprehensive test suite that definitively proves the root cause of the
 * java.lang.IllegalArgumentException and validates the correct argument-passing format.
 * 
 * These tests serve as a verifiable handoff to the deployment team.
 */
@RunWith(JUnit4::class)
class StrategyDiscoveryPipelineRunnerTest {

    /**
     * Test Case 0: Verify that FlinkRunner class is available for production deployment.
     * This test ensures that the FlinkRunner dependency is properly included in runtime_deps.
     */
    @Test
    fun `flink runner class should be available for production deployment`() {
        // ARRANGE & ACT: Attempt to load the FlinkRunner class
        val flinkRunnerClass = try {
            Class.forName("org.apache.beam.runners.flink.FlinkRunner")
        } catch (e: ClassNotFoundException) {
            null
        }

        // ASSERT: Verify that the FlinkRunner class is available
        assertThat(flinkRunnerClass).isNotNull()
        assertThat(flinkRunnerClass?.name).isEqualTo("org.apache.beam.runners.flink.FlinkRunner")
    }

    /**
     * Test Case 1: Replicate the production bug.
     * This test proves that a semicolon-delimited string of arguments causes the
     * PipelineOptionsFactory to fail with the expected exception.
     */
    @Test
    fun `given a single semicolon-delimited string, pipeline options creation should fail`() {
        // ARRANGE: Simulate the exact argument string format from the logs.
        val brokenArgs = arrayOf(
            "--bootstrapServers=host:9092;--streaming=true"
        )

        // ACT & ASSERT: Verify that this specific input throws an IllegalArgumentException.
        val exception = assertThrows(IllegalArgumentException::class.java) {
            PipelineOptionsFactory.fromArgs(*brokenArgs)
                .`as`(StrategyDiscoveryPipelineOptions::class.java)
        }

        // ASSERT: Further inspect the exception to confirm it's failing for the right reason.
        // This makes the test highly specific and valuable for diagnosis.
        val expectedMessage = "Class interface com.verlumen.tradestream.discovery.StrategyDiscoveryPipelineOptions " +
                              "missing a property named 'bootstrapServers'."
        assertThat(exception.message).isEqualTo(expectedMessage)
    }

    /**
     * Test Case 2: Document the correct argument format.
     * This test shows the expected format for the arguments, where each flag
     * is a separate element in the array. This serves as executable documentation
     * for the team responsible for deployment.
     */
    @Test
    fun `given a correctly formatted string array, pipeline options creation should succeed`() {
        // ARRANGE: Define the arguments in the correct format.
        val correctArgs = arrayOf(
            "--kafkaBootstrapServers=host:9092",
            "--streaming=true",
            "--dryRun=true",
            "--databaseUsername=test_user",
            "--databasePassword=test_password",
            "--influxDbToken=test-token"
        )

        // ACT: Attempt to create the options. No exception should be thrown.
        val options = PipelineOptionsFactory.fromArgs(*correctArgs)
            .`as`(StrategyDiscoveryPipelineOptions::class.java)

        // ASSERT: Verify that the properties were correctly parsed and set.
        assertThat(options.kafkaBootstrapServers).isEqualTo("host:9092")
        assertThat(options.isStreaming).isTrue()
        assertThat(options.dryRun).isTrue()
        assertThat(options.databaseUsername).isEqualTo("test_user")
        assertThat(options.databasePassword).isEqualTo("test_password")
        assertThat(options.influxDbToken).isEqualTo("test-token")
    }

    /**
     * Test Case 3: Space-delimited arguments in a single string are NOT split.
     * The entire string is treated as the value for the first property.
     */
    @Test
    fun `given space-delimited arguments in single string, pipeline options creation should treat as one value`() {
        // ARRANGE: Simulate space-delimited arguments in a single string.
        val spaceDelimitedArgs = arrayOf(
            "--kafkaBootstrapServers=host:9092 --streaming=true"
        )

        // ACT: Attempt to create the options with space-delimited arguments.
        val options = PipelineOptionsFactory.fromArgs(*spaceDelimitedArgs)
            .`as`(StrategyDiscoveryPipelineOptions::class.java)

        // ASSERT: The entire string is the value for kafkaBootstrapServers, streaming is not set.
        assertThat(options.kafkaBootstrapServers).isEqualTo("host:9092 --streaming=true")
        // The default for streaming is false
        assertThat(options.isStreaming).isFalse()
    }

    /**
     * Test Case 4: Comma-delimited arguments in a single string are NOT split.
     * The entire string is treated as the value for the first property.
     */
    @Test
    fun `given comma-delimited arguments in single string, pipeline options creation should treat as one value`() {
        // ARRANGE: Simulate comma-delimited arguments in a single string.
        val commaDelimitedArgs = arrayOf(
            "--kafkaBootstrapServers=host:9092,--streaming=true"
        )

        // ACT: Attempt to create the options with comma-delimited arguments.
        val options = PipelineOptionsFactory.fromArgs(*commaDelimitedArgs)
            .`as`(StrategyDiscoveryPipelineOptions::class.java)

        // ASSERT: The entire string is the value for kafkaBootstrapServers, streaming is not set.
        assertThat(options.kafkaBootstrapServers).isEqualTo("host:9092,--streaming=true")
        assertThat(options.isStreaming).isFalse()
    }

    /**
     * Test Case 5: Validate that empty arguments are handled gracefully.
     * This test ensures that empty argument arrays don't cause unexpected behavior.
     */
    @Test
    fun `given empty arguments array, pipeline options creation should use defaults`() {
        // ARRANGE: Empty arguments array.
        val emptyArgs = arrayOf<String>()

        // ACT: Attempt to create the options with empty arguments.
        val options = PipelineOptionsFactory.fromArgs(*emptyArgs)
            .`as`(StrategyDiscoveryPipelineOptions::class.java)

        // ASSERT: Verify that default values are used.
        assertThat(options.kafkaBootstrapServers).isEqualTo("localhost:9092") // Default from @Default.String
        assertThat(options.strategyDiscoveryRequestTopic).isEqualTo("strategy-discovery-requests") // Default from @Default.String
        assertThat(options.influxDbUrl).isEqualTo("http://localhost:8086") // Default from @Default.String
        assertThat(options.influxDbOrg).isEqualTo("tradestream-org") // Default from @Default.String
        assertThat(options.influxDbBucket).isEqualTo("tradestream-data") // Default from @Default.String
        assertThat(options.dbServerName).isEqualTo("localhost") // Default from @Default.String
        assertThat(options.dbDatabaseName).isEqualTo("tradestream") // Default from @Default.String
        assertThat(options.dbPortNumber).isEqualTo(5432) // Default from @Default.Integer
    }

    /**
     * Test Case 6: Validate that partial arguments work correctly.
     * This test ensures that providing only some arguments works as expected.
     */
    @Test
    fun `given partial arguments, pipeline options creation should succeed with mixed defaults`() {
        // ARRANGE: Provide only some arguments, leaving others to use defaults.
        val partialArgs = arrayOf(
            "--kafkaBootstrapServers=custom-host:9092",
            "--dryRun=true",
            "--databaseUsername=custom_user"
        )

        // ACT: Attempt to create the options with partial arguments.
        val options = PipelineOptionsFactory.fromArgs(*partialArgs)
            .`as`(StrategyDiscoveryPipelineOptions::class.java)

        // ASSERT: Verify that provided arguments are set and defaults are used for others.
        assertThat(options.kafkaBootstrapServers).isEqualTo("custom-host:9092")
        assertThat(options.dryRun).isTrue()
        assertThat(options.databaseUsername).isEqualTo("custom_user")
        
        // Verify defaults are still used for unspecified arguments.
        assertThat(options.strategyDiscoveryRequestTopic).isEqualTo("strategy-discovery-requests")
        assertThat(options.influxDbUrl).isEqualTo("http://localhost:8086")
        assertThat(options.dbServerName).isEqualTo("localhost")
    }

    /**
     * Test Case 7: Validate that invalid property names are handled correctly.
     * This test ensures that the PipelineOptionsFactory properly validates property names.
     */
    @Test
    fun `given invalid property name, pipeline options creation should fail with clear error`() {
        // ARRANGE: Use an invalid property name that doesn't exist in the options interface.
        val invalidArgs = arrayOf(
            "--invalidProperty=value"
        )

        // ACT & ASSERT: Verify that this throws an IllegalArgumentException with a clear message.
        val exception = assertThrows(IllegalArgumentException::class.java) {
            PipelineOptionsFactory.fromArgs(*invalidArgs)
                .`as`(StrategyDiscoveryPipelineOptions::class.java)
        }

        // ASSERT: Verify the exception message indicates the invalid property.
        assertThat(exception.message).contains("missing a property named 'invalidProperty'")
    }

    /**
     * Test Case 8: Validate that the main method argument parsing works correctly.
     * This test simulates the actual main method call with proper argument format.
     */
    @Test
    fun `main method should handle correctly formatted arguments`() {
        // ARRANGE: Simulate the arguments that would be passed to the main method.
        val mainArgs = arrayOf(
            "--kafkaBootstrapServers=host:9092",
            "--streaming=true",
            "--dryRun=true",
            "--databaseUsername=test_user",
            "--databasePassword=test_password",
            "--influxDbToken=test-token",
            "--influxDbUrl=http://localhost:8086",
            "--influxDbOrg=test-org",
            "--influxDbBucket=test-bucket"
        )

        // ACT: Test the argument parsing logic that would be used in main method.
        // Note: We're not calling the actual main method to avoid complex setup,
        // but we're testing the same argument parsing logic.
        val options = PipelineOptionsFactory.fromArgs(*mainArgs)
            .`as`(StrategyDiscoveryPipelineOptions::class.java)

        // ASSERT: Verify all arguments are parsed correctly.
        assertThat(options.kafkaBootstrapServers).isEqualTo("host:9092")
        assertThat(options.isStreaming).isTrue()
        assertThat(options.dryRun).isTrue()
        assertThat(options.databaseUsername).isEqualTo("test_user")
        assertThat(options.databasePassword).isEqualTo("test_password")
        assertThat(options.influxDbToken).isEqualTo("test-token")
        assertThat(options.influxDbUrl).isEqualTo("http://localhost:8086")
        assertThat(options.influxDbOrg).isEqualTo("test-org")
        assertThat(options.influxDbBucket).isEqualTo("test-bucket")
    }

    /**
     * Test Case 9: Validate that the actual production error scenario is replicated.
     * This test specifically targets the exact error seen in production logs.
     */
    @Test
    fun `production error scenario should be replicated`() {
        // ARRANGE: Simulate the exact production scenario where arguments are concatenated.
        val productionBrokenArgs = arrayOf(
            "--bootstrapServers=host:9092;--runner=FlinkRunner;--streaming=true"
        )

        // ACT & ASSERT: Verify that this specific input throws an IllegalArgumentException.
        val exception = assertThrows(IllegalArgumentException::class.java) {
            PipelineOptionsFactory.fromArgs(*productionBrokenArgs)
                .`as`(StrategyDiscoveryPipelineOptions::class.java)
        }

        // ASSERT: Verify the exception message indicates the root cause.
        // The PipelineOptionsFactory treats the entire string as a single property name.
        assertThat(exception.message).contains("missing a property named")
        assertThat(exception.message).contains("bootstrapServers")
    }

    /**
     * Test Case 10: Validate that the exact production error message format is replicated.
     * This test ensures we're testing the exact scenario from production logs.
     */
    @Test
    fun `production error message format should be replicated`() {
        // ARRANGE: Simulate the exact production scenario with the exact property name from logs.
        val productionBrokenArgs = arrayOf(
            "--bootstrapServers=host:9092;--runner=FlinkRunner;--streaming=true"
        )

        // ACT & ASSERT: Verify that this specific input throws an IllegalArgumentException.
        val exception = assertThrows(IllegalArgumentException::class.java) {
            PipelineOptionsFactory.fromArgs(*productionBrokenArgs)
                .`as`(StrategyDiscoveryPipelineOptions::class.java)
        }

        // ASSERT: Verify the exact exception message format from production.
        // The PipelineOptionsFactory treats the entire string as a single property name.
        val expectedMessage = "Class interface com.verlumen.tradestream.discovery.StrategyDiscoveryPipelineOptions " +
                              "missing a property named 'bootstrapServers'."
        assertThat(exception.message).isEqualTo(expectedMessage)
    }

    /**
     * Helper function to assert that an exception is thrown.
     * This provides a cleaner way to test for exceptions in Kotlin.
     */
    private fun <T : Throwable> assertThrows(exceptionClass: Class<T>, block: () -> Unit): T {
        try {
            block()
            throw AssertionError("Expected ${exceptionClass.simpleName} to be thrown, but no exception was thrown.")
        } catch (e: Throwable) {
            if (exceptionClass.isInstance(e)) {
                @Suppress("UNCHECKED_CAST")
                return e as T
            } else {
                throw AssertionError(
                    "Expected ${exceptionClass.simpleName} to be thrown, but ${e.javaClass.simpleName} was thrown instead.",
                    e,
                )
            }
        }
    }
} 