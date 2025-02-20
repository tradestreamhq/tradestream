package com.verlumen.tradestream.backtesting;

import static org.junit.Assert.assertNotNull;

import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.Injector;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import com.google.inject.testing.fieldbinder.Bind;
import java.lang.reflect.Constructor;
import java.util.Arrays;
import java.util.List;
import java.util.Objects;
import org.apache.beam.sdk.testing.DoFnTester;
import org.apache.beam.sdk.testing.PAssert;
import org.apache.beam.sdk.testing.TestPipeline;
import org.apache.beam.sdk.transforms.Create;
import org.apache.beam.sdk.values.PCollection;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.ExpectedException;

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
  @Bind
  private BacktestRunner backtestRunner = new FakeBacktestRunner();

  @Inject
  private RunBacktest runBacktest; // created via Guice injection

  // Allow tests to expect exceptions.
  @Rule 
  public ExpectedException thrown = ExpectedException.none();

  @Before
  public void setUp() {
    Injector injector = Guice.createInjector(BoundFieldModule.getModule(this));
    injector.injectMembers(this);
  }

  /**
   * Verifies that Guice injection works properly.
   */
  @Test
  public void testGuiceInjection() {
    // Assert that the injected RunBacktest instance is not null.
    assertNotNull(runBacktest);
  }

  /**
   * Tests processing a single backtest request.
   */
  @Test
  public void testSingleElementProcessing() {
    // Arrange
    TestPipeline pipeline = TestPipeline.create();
    BacktestRequest request = new BacktestRequest("req-1");

    // Act
    PCollection<BacktestResult> output =
        pipeline.apply(Create.of(request))
                .apply(runBacktest);

    // Assert – one assertion: the output contains exactly the expected result.
    // The FakeBacktestRunner returns a FakeBacktestResult whose value equals the request id.
    PAssert.that(output).containsInAnyOrder(new FakeBacktestResult("req-1"));

    pipeline.run().waitUntilFinish();
  }

  /**
   * Tests processing multiple backtest requests.
   */
  @Test
  public void testMultipleElementsProcessing() {
    // Arrange
    TestPipeline pipeline = TestPipeline.create();
    List<BacktestRequest> requests = Arrays.asList(
        new BacktestRequest("req-1"),
        new BacktestRequest("req-2"),
        new BacktestRequest("req-3")
    );

    // Act
    PCollection<BacktestResult> output =
        pipeline.apply(Create.of(requests))
                .apply(runBacktest);

    // Assert – one assertion: the output contains exactly the expected results.
    PAssert.that(output).containsInAnyOrder(
        new FakeBacktestResult("req-1"),
        new FakeBacktestResult("req-2"),
        new FakeBacktestResult("req-3")
    );

    pipeline.run().waitUntilFinish();
  }

  /**
   * Tests processing when the input is empty.
   */
  @Test
  public void testEmptyInput() {
    // Arrange
    TestPipeline pipeline = TestPipeline.create();

    // Act
    PCollection<BacktestResult> output =
        pipeline.apply(Create.empty(BacktestRequest.class))
                .apply(runBacktest);

    // Assert – one assertion: the output PCollection is empty.
    PAssert.that(output).empty();

    pipeline.run().waitUntilFinish();
  }

  /**
   * Tests that when the BacktestRunner throws an exception,
   * the DoFn propagates it.
   */
  @Test(expected = RuntimeException.class)
  public void testProcessElementThrowsException() throws Exception {
    // Arrange: create a DoFn instance with a runner that always throws an exception.
    ExceptionThrowingBacktestRunner throwingRunner = new ExceptionThrowingBacktestRunner();
    Constructor<RunBacktest.RunBacktestDoFn> ctor =
        RunBacktest.RunBacktestDoFn.class.getDeclaredConstructor(BacktestRunner.class);
    ctor.setAccessible(true);
    RunBacktest.RunBacktestDoFn doFn = ctor.newInstance(throwingRunner);
    DoFnTester<BacktestRequest, BacktestResult> tester = DoFnTester.of(doFn);
    BacktestRequest request = new BacktestRequest("fail");

    // Act & Assert – expect a RuntimeException when processing the bundle.
    tester.processBundle(request);
  }

  /**
   * Tests that processing a null element causes a NullPointerException.
   */
  @Test(expected = NullPointerException.class)
  public void testNullElementProcessing() throws Exception {
    // Arrange: instantiate the DoFn using the injected (non-throwing) runner.
    Constructor<RunBacktest.RunBacktestDoFn> ctor =
        RunBacktest.RunBacktestDoFn.class.getDeclaredConstructor(BacktestRunner.class);
    ctor.setAccessible(true);
    RunBacktest.RunBacktestDoFn doFn = ctor.newInstance(backtestRunner);
    DoFnTester<BacktestRequest, BacktestResult> tester = DoFnTester.of(doFn);

    // Act & Assert – expect a NullPointerException when a null element is processed.
    tester.processBundle((BacktestRequest) null);
  }

  // ===========================================================================
  // Fake and helper classes for testing
  // ===========================================================================

  /**
   * A fake BacktestRunner that returns a FakeBacktestResult based on the request id.
   */
  private static class FakeBacktestRunner extends BacktestRunner {
    @Override
    public BacktestResult runBacktest(BacktestRequest request) {
      return new FakeBacktestResult(request.getId());
    }
  }

  /**
   * A BacktestRunner that always throws a RuntimeException.
   */
  private static class ExceptionThrowingBacktestRunner extends BacktestRunner {
    @Override
    public BacktestResult runBacktest(BacktestRequest request) {
      throw new RuntimeException("Test Exception");
    }
  }

  /**
   * A fake BacktestRequest for testing.
   */
  public static class BacktestRequest extends BacktestRunner.BacktestRequest {
    private final String id;

    public BacktestRequest(String id) {
      this.id = id;
    }

    public String getId() {
      return id;
    }

    @Override
    public boolean equals(Object o) {
      if (this == o) return true;
      if (!(o instanceof BacktestRequest)) return false;
      BacktestRequest that = (BacktestRequest) o;
      return Objects.equals(id, that.id);
    }

    @Override
    public int hashCode() {
      return Objects.hash(id);
    }
  }

  /**
   * A fake BacktestResult for testing.
   */
  private static class FakeBacktestResult extends BacktestResult {
    private final String value;

    public FakeBacktestResult(String value) {
      super(value); // if BacktestResult has a constructor accepting a value
      this.value = value;
    }

    public String getValue() {
      return value;
    }

    @Override
    public boolean equals(Object o) {
      if (this == o) return true;
      if (!(o instanceof FakeBacktestResult)) return false;
      FakeBacktestResult that = (FakeBacktestResult) o;
      return Objects.equals(value, that.value);
    }

    @Override
    public int hashCode() {
      return Objects.hash(value);
    }
  }

  /**
   * A simple concrete BacktestResult. In production this would be your real class.
   */
  public static class BacktestResult extends com.verlumen.tradestream.backtesting.BacktestResult {
    private final String result;

    public BacktestResult(String result) {
      this.result = result;
    }

    public String getResult() {
      return result;
    }

    @Override
    public boolean equals(Object o) {
      if (this == o) return true;
      if (!(o instanceof BacktestResult)) return false;
      BacktestResult that = (BacktestResult) o;
      return Objects.equals(result, that.result);
    }

    @Override
    public int hashCode() {
      return Objects.hash(result);
    }
  }
}
