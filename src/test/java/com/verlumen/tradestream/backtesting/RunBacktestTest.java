package com.verlumen.tradestream.backtesting;

import static com.google.common.truth.Truth.assertThat;
import static org.junit.Assert.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.testing.fieldbinder.Bind;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import com.verlumen.tradestream.backtesting.BacktestRunner.BacktestRequest; // Correct import!
import com.verlumen.tradestream.strategies.StrategyType;
import java.time.Duration;
import java.time.ZonedDateTime;

import org.apache.beam.sdk.testing.PAssert;
import org.apache.beam.sdk.testing.TestPipeline;
import org.apache.beam.sdk.transforms.Create;
import org.apache.beam.sdk.values.PCollection;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.mockito.Mock;
import org.mockito.junit.MockitoJUnit;
import org.mockito.junit.MockitoRule;
import org.ta4j.core.Bar;
import org.ta4j.core.BaseBarSeries;
import org.ta4j.core.BaseStrategy;
import org.ta4j.core.Strategy;

import java.util.Arrays;
import java.util.List;

/**
 * Test suite for the RunBacktest transform.
 *
 * <p>This suite uses:
 * <ul>
 *   <li>the AAA pattern for clear Arrange-Act-Assert separation,
 *   <li>BoundFieldModule (boundfieldinjector) with Guice to inject the test instance,
 *   <li>one assertion per test case.
 * </ul>
 */
@RunWith(JUnit4.class)
public class RunBacktestTest {

    // Use Mockito and BoundFieldModule to inject a mocked runner.
    @Bind private BacktestRunner backtestRunner = new FakeBacktestRunner();

    @Inject private RunBacktest runBacktest; // created via Guice injection

    // Allow tests to expect exceptions.
    @Rule public MockitoRule mockitoRule = MockitoJUnit.rule();

  @Rule
  public final TestPipeline pipeline = TestPipeline.create();

    @Before
    public void setUp() {
        Guice.createInjector(BoundFieldModule.of(this)).injectMembers(this);
    }

    /** Verifies that Guice injection works properly. */
    @Test
    public void testGuiceInjection() {
        // Assert that the injected RunBacktest instance is not null.
        assertNotNull(runBacktest);
    }

    /** Tests processing a single backtest request. */
    @Test
    public void testSingleElementProcessing() {
        // Arrange

        BacktestRequest request = BacktestRequest.builder().setId("req-1").build();

        // Act
        PCollection<BacktestResult> output = pipeline.apply(Create.of(request)).apply(runBacktest);

        // Assert – one assertion: the output contains exactly the expected result.
        // The FakeBacktestRunner returns a BacktestResult whose value equals the request id.
        PAssert.that(output).containsInAnyOrder(BacktestResult.newBuilder().setOverallScore(0.5).setId("req-1").build()); // Using builder!

        pipeline.run().waitUntilFinish();
    }

    /** Tests processing multiple backtest requests. */
    @Test
    public void testMultipleElementsProcessing() {
        // Arrange
        List<BacktestRunner.BacktestRequest> requests = Arrays.asList(
            BacktestRequest.builder().setId("req-1").build(),
            BacktestRequest.builder().setId("req-2").build(),
            BacktestRequest.builder().setId("req-3").build()
        );

        // Act
        PCollection<BacktestResult> output = pipeline.apply(Create.of(requests)).apply(runBacktest);

        // Assert – one assertion: the output contains exactly the expected results.
        PAssert.that(output)
            .containsInAnyOrder(
                BacktestResult.newBuilder().setOverallScore(0.5).setId("req-1").build(), // Using builder!
                BacktestResult.newBuilder().setOverallScore(0.5).setId("req-2").build(), // Using builder!
                BacktestResult.newBuilder().setOverallScore(0.5).setId("req-3").build()); // Using builder!

        pipeline.run().waitUntilFinish();
    }

    /** Tests processing when the input is empty. */
    @Test
    public void testEmptyInput() {
        // Arrange and Act
        PCollection<BacktestResult> output =
            pipeline
                .apply(Create.empty(BacktestRunner.BacktestRequest.class))
                .apply(runBacktest);

        // Assert – one assertion: the output PCollection is empty.
        PAssert.that(output).empty();

        pipeline.run().waitUntilFinish();
    }

    /**
     * Tests that when the BacktestRunner throws an exception, the DoFn propagates it.
     */
        @Test
        public void testProcessElementThrowsException() {
           // Arrange
           BacktestRequest request = BacktestRequest.builder().setId("fail").build();

           // Configure the mock runner to throw an exception
           when(backtestRunner.runBacktest(any(BacktestRunner.BacktestRequest.class))).thenThrow(new RuntimeException("Test Exception"));

           // Act & Assert - Expect a RuntimeException when processing the bundle
           assertThrows(RuntimeException.class, () -> pipeline.apply(Create.of(request)).apply(runBacktest));
       }

     /**
      * Tests that processing a null element causes a NullPointerException.
      */
      @Test(expected = NullPointerException.class)
      public void testNullElementProcessing() {
          // Arrange & Act
          PCollection<BacktestResult> output = pipeline.apply(Create.of((BacktestRequest) null)).apply(runBacktest);

          // Assert
          pipeline.run().waitUntilFinish();
      }


    // ===========================================================================
    // Fake and helper classes for testing
    // ===========================================================================

    /** A fake BacktestRunner that returns a BacktestResult based on the request id. */
    private static class FakeBacktestRunner implements BacktestRunner { //Helper class

        private final String id;

        FakeBacktestRunner(String id){
            this.id = id;
        }
        FakeBacktestRunner(){
            this.id = "";
        }

        @Override
        public BacktestResult runBacktest(BacktestRequest request) {
            return BacktestResult.newBuilder().setOverallScore(0.5).setId(request.getId()).build(); // Using builder!
        }
    }

    /** A BacktestRunner that always throws a RuntimeException. */
    private static class ExceptionThrowingBacktestRunner implements BacktestRunner {
        @Override
        public BacktestResult runBacktest(BacktestRequest request) {
            throw new RuntimeException("Test Exception");
        }
    }
}
