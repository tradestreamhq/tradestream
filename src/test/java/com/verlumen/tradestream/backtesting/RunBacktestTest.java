package com.verlumen.tradestream.backtesting;

import static org.junit.Assert.assertNotNull;

import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.testing.fieldbinder.Bind;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import com.verlumen.tradestream.strategies.StrategyType;
import java.util.Arrays;
import java.util.List;
import org.apache.beam.sdk.testing.DoFnTester;
import org.apache.beam.sdk.testing.PAssert;
import org.apache.beam.sdk.testing.TestPipeline;
import org.apache.beam.sdk.transforms.Create;
import org.apache.beam.sdk.values.PCollection;
import org.joda.time.Duration;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.ExpectedException;
import org.ta4j.core.BarSeries;
import org.ta4j.core.Strategy;

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
public class RunBacktestTest {

  // Use BoundFieldModule to inject our fake runner.
  @Bind private BacktestRunner backtestRunner = new FakeBacktestRunner();

  @Inject private RunBacktest runBacktest; // created via Guice injection

  // Allow tests to expect exceptions.
  @Rule public ExpectedException thrown = ExpectedException.none();

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
    TestPipeline pipeline = TestPipeline.create();
    BacktestRequest request = BacktestRequest.builder().setId("req-1").build();

    // Act
    PCollection<BacktestResult> output = pipeline.apply(Create.of(request)).apply(runBacktest);

    // Assert – one assertion: the output contains exactly the expected result.
    // The FakeBacktestRunner returns a BacktestResult whose value equals the request id.
      PAssert.that(output).containsInAnyOrder(BacktestResult.create("req-1"));

    pipeline.run().waitUntilFinish();
  }

  /** Tests processing multiple backtest requests. */
  @Test
  public void testMultipleElementsProcessing() {
    // Arrange
    TestPipeline pipeline = TestPipeline.create();
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
            BacktestResult.create("req-1"),
            BacktestResult.create("req-2"),
            BacktestResult.create("req-3"));

    pipeline.run().waitUntilFinish();
  }

  /** Tests processing when the input is empty. */
  @Test
  public void testEmptyInput() {
    // Arrange
    TestPipeline pipeline = TestPipeline.create();

    // Act
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
    @Test(expected = RuntimeException.class)
    public void testProcessElementThrowsException() throws Exception {
        // Arrange: create a DoFn instance with a runner that always throws an exception.
        ExceptionThrowingBacktestRunner throwingRunner = new ExceptionThrowingBacktestRunner();

      RunBacktest.RunBacktestDoFn doFn = new RunBacktest.RunBacktestDoFn(throwingRunner);

        DoFnTester<BacktestRunner.BacktestRequest, BacktestResult> tester = DoFnTester.of(doFn);
        BacktestRunner.BacktestRequest request = BacktestRequest.builder().setId("fail").build();

        // Act & Assert – expect a RuntimeException when processing the bundle.
        tester.processBundle(request);
    }

    /**
     * Tests that processing a null element causes a NullPointerException.
     */
    @Test(expected = NullPointerException.class)
    public void testNullElementProcessing() throws Exception {
        // Arrange: instantiate the DoFn using the injected (non-throwing) runner.

        RunBacktest.RunBacktestDoFn doFn = new RunBacktest.RunBacktestDoFn(backtestRunner);
        DoFnTester<BacktestRunner.BacktestRequest, BacktestResult> tester = DoFnTester.of(doFn);

        // Act & Assert – expect a NullPointerException when a null element is processed.
        tester.processBundle((BacktestRunner.BacktestRequest) null);
    }


  // ===========================================================================
  // Fake and helper classes for testing
  // ===========================================================================

  /** A fake BacktestRunner that returns a BacktestResult based on the request id. */
  private static class FakeBacktestRunner implements BacktestRunner {

      private final String id;

      FakeBacktestRunner(String id){
          this.id = id;
      }
      FakeBacktestRunner(){
          this.id = "";
      }

      @Override
      public BacktestResult runBacktest(BacktestRequest request) {
          return BacktestResult.create(request.toString());
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
