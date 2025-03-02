package com.verlumen.tradestream.backtesting;

import static com.google.common.truth.Truth.assertThat;
import static org.junit.Assert.assertThrows;
import static org.junit.Assert.assertNotNull;

import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.testing.fieldbinder.Bind;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.marketdata.Candle;
import com.verlumen.tradestream.strategies.Strategy;
import com.verlumen.tradestream.strategies.StrategyType;
import org.apache.beam.sdk.Pipeline.PipelineExecutionException;
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

import java.util.Arrays;
import java.util.List;
import java.util.ArrayList;
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

    @Before
    public void setUp() {
        Guice.createInjector(BoundFieldModule.of(this)).injectMembers(this);
    }

    @Test
    public void testGuiceInjection() {
        assertNotNull(runBacktest);
    }

    @Test
    public void testSingleElementProcessing() {
        BacktestRequest request = createDummyRequest();

        PCollection<BacktestResult> output = pipeline
            .apply(Create.of(request))
            .apply(runBacktest);

        PAssert.that(output)
            .containsInAnyOrder(BacktestResult.newBuilder().setStrategyScore(0.5).build());

        pipeline.run().waitUntilFinish();
    }

    @Test
    public void testMultipleElementsProcessing() {
        List<BacktestRequest> requests = Arrays.asList(
            createDummyRequest(),
            createDummyRequest(),
            createDummyRequest()
        );

        PCollection<BacktestResult> output = pipeline
            .apply(Create.of(requests))
            .apply(runBacktest);

        PAssert.that(output)
            .containsInAnyOrder(
                BacktestResult.newBuilder().setStrategyScore(0.5).build(),
                BacktestResult.newBuilder().setStrategyScore(0.5).build(),
                BacktestResult.newBuilder().setStrategyScore(0.5).build()
            );

        pipeline.run().waitUntilFinish();
    }

    @Test
    public void testEmptyInput() {
        PCollection<BacktestResult> output = pipeline
            .apply(Create.empty(SerializableCoder.of(BacktestRequest.class)))
            .apply(runBacktest);

        PAssert.that(output).empty();
        pipeline.run().waitUntilFinish();
    }

    @Test
    public void testNullElementProcessing() {
        // When using null in a Beam pipeline, we need to catch the exception differently
        assertThrows(PipelineExecutionException.class, () -> {
            pipeline
                .apply(Create.of((BacktestRequest) null))
                .apply(runBacktest);

            pipeline.run().waitUntilFinish();
        });
    }

    @Test
    public void testProcessElementThrowsException() {
        // Redefine the field with new value
        this.backtestRunnerFactory = new SerializableExceptionThrowingBacktestRunnerFactory();
        // Re-inject
        Guice.createInjector(BoundFieldModule.of(this)).injectMembers(this);

        // Setup the pipeline and execute
        BacktestRequest request = createDummyRequest();
        pipeline
            .apply(Create.of(request))
            .apply(runBacktest);

        // Assert the pipeline throws an exception when run
        assertThrows(PipelineExecutionException.class, () -> {
            pipeline.run().waitUntilFinish();
        });
    }

    private BacktestRequest createDummyRequest() {
        return BacktestRequest.newBuilder()
            .addCandles(Candle.newBuilder()
                .setCurrencyPair("BTC/USD")
                .setOpen(100.0)
                .setHigh(110.0)
                .setLow(90.0)
                .setClose(105.0)
                .setVolume(1000.0)
                .build())
            .setStrategy(Strategy.newBuilder()
                .setType(StrategyType.SMA_RSI)
                .build())
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

    private static class FakeBacktestRunner implements BacktestRunner {
        @Override
        public BacktestResult runBacktest(BacktestRequest request) throws InvalidProtocolBufferException {
            return BacktestResult.newBuilder().setStrategyScore(0.5).build();
        }
    }

    private static class ExceptionThrowingBacktestRunner implements BacktestRunner {
        @Override
        public BacktestResult runBacktest(BacktestRequest request) throws InvalidProtocolBufferException {
            throw new RuntimeException("Test Exception");
        }
    }
}
