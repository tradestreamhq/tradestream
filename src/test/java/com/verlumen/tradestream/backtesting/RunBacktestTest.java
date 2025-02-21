package com.verlumen.tradestream.backtesting;

import static com.google.common.truth.Truth.assertThat;
import static org.junit.Assert.assertThrows;
import static org.junit.Assert.assertNotNull;

import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.testing.fieldbinder.Bind;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import com.verlumen.tradestream.strategies.StrategyType;
import org.apache.beam.sdk.coders.SerializableCoder;
import org.apache.beam.sdk.testing.PAssert;
import org.apache.beam.sdk.testing.TestPipeline;
import org.apache.beam.sdk.transforms.Create;
import org.apache.beam.sdk.values.PCollection;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.mockito.junit.MockitoJUnit;
import org.mockito.junit.MockitoRule;
import org.ta4j.core.BaseBarSeries;
import org.ta4j.core.BaseStrategy;
import org.ta4j.core.Strategy;

import java.util.Arrays;
import java.util.List;
import java.io.Serializable;

@RunWith(JUnit4.class)
public class RunBacktestTest {
    @Bind 
    private RunBacktest.SerializableBacktestRunnerFactory backtestRunnerFactory = 
        new SerializableFakeBacktestRunnerFactory();

    @Inject 
    private RunBacktest runBacktest;

    @Rule 
    public MockitoRule mockitoRule = MockitoJUnit.rule();

    @Rule
    public final TestPipeline pipeline = TestPipeline.create();

    private BaseBarSeries dummySeries;
    private SerializableStrategy dummyStrategy;

    @Before
    public void setUp() {
        dummySeries = new BaseBarSeries("dummy");
        dummyStrategy = new SerializableStrategy();
        Guice.createInjector(BoundFieldModule.of(this)).injectMembers(this);
    }

    @Test
    public void testGuiceInjection() {
        assertNotNull(runBacktest);
    }

    @Test
    public void testSingleElementProcessing() {
        BacktestRunner.BacktestRequest request = BacktestRunner.BacktestRequest.builder()
            .setBarSeries(dummySeries)
            .setStrategy(dummyStrategy)
            .setStrategyType(StrategyType.SMA_RSI)
            .build();

        PCollection<BacktestResult> output = pipeline
            .apply(Create.of(request))
            .apply(runBacktest);

        PAssert.that(output)
            .containsInAnyOrder(BacktestResult.newBuilder().setOverallScore(0.5).build());

        pipeline.run().waitUntilFinish();
    }

    @Test
    public void testMultipleElementsProcessing() {
        List<BacktestRunner.BacktestRequest> requests = Arrays.asList(
            createDummyRequest(),
            createDummyRequest(),
            createDummyRequest()
        );

        PCollection<BacktestResult> output = pipeline
            .apply(Create.of(requests))
            .apply(runBacktest);

        PAssert.that(output)
            .containsInAnyOrder(
                BacktestResult.newBuilder().setOverallScore(0.5).build(),
                BacktestResult.newBuilder().setOverallScore(0.5).build(),
                BacktestResult.newBuilder().setOverallScore(0.5).build()
            );

        pipeline.run().waitUntilFinish();
    }

    @Test
    public void testEmptyInput() {
        PCollection<BacktestResult> output = pipeline
            .apply(Create.empty(SerializableCoder.of(BacktestRunner.BacktestRequest.class)))
            .apply(runBacktest);

        PAssert.that(output).empty();
        pipeline.run().waitUntilFinish();
    }

    @Test
    public void testProcessElementThrowsException() {
        BacktestRunner.BacktestRequest request = createDummyRequest();
        backtestRunnerFactory = new SerializableExceptionThrowingBacktestRunnerFactory();
        Guice.createInjector(BoundFieldModule.of(this)).injectMembers(this);

        assertThrows(RuntimeException.class, 
            () -> pipeline.apply(Create.of(request)).apply(runBacktest));
    }

    @Test
    public void testNullElementProcessing() {
        PCollection<BacktestResult> output = pipeline
            .apply(Create.of((BacktestRunner.BacktestRequest) null))
            .apply(runBacktest);
            
        pipeline.run();
        // Pipeline should fail with NullPointerException
    }

    private BacktestRunner.BacktestRequest createDummyRequest() {
        return BacktestRunner.BacktestRequest.builder()
            .setBarSeries(dummySeries)
            .setStrategy(dummyStrategy)
            .setStrategyType(StrategyType.SMA_RSI)
            .build();
    }

    private static class SerializableFakeBacktestRunnerFactory 
            implements RunBacktest.SerializableBacktestRunnerFactory {
        @Override
        public BacktestRunner create() {
            return new FakeBacktestRunner();
        }
    }

    private static class SerializableExceptionThrowingBacktestRunnerFactory 
            implements RunBacktest.SerializableBacktestRunnerFactory {
        @Override
        public BacktestRunner create() {
            return new ExceptionThrowingBacktestRunner();
        }
    }

    private static class SerializableStrategy implements Strategy, Serializable {
        @Override
        public boolean shouldEnter(int index) {
            return false;
        }

        @Override
        public boolean shouldExit(int index) {
            return false;
        }

        @Override
        public int getUnstableBars() {
            return 0;
        }
    }

    private static class FakeBacktestRunner implements BacktestRunner {
        @Override
        public BacktestResult runBacktest(BacktestRunner.BacktestRequest request) {
            return BacktestResult.newBuilder().setOverallScore(0.5).build();
        }
    }

    private static class ExceptionThrowingBacktestRunner implements BacktestRunner {
        @Override
        public BacktestResult runBacktest(BacktestRunner.BacktestRequest request) {
            throw new RuntimeException("Test Exception");
        }
    }
}
