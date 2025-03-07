package com.verlumen.tradestream.signals;

import static org.mockito.Mockito.*;

import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.testing.fieldbinder.Bind;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import org.apache.beam.sdk.testing.TestPipeline;
import org.apache.beam.sdk.transforms.Create;
import org.apache.beam.sdk.values.KV;
import org.apache.beam.sdk.values.PCollection;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.mockito.Mock;
import org.mockito.junit.MockitoJUnit;
import org.mockito.junit.MockitoRule;
import org.mockito.quality.Strictness;

@RunWith(JUnit4.class)
public class PublishTradeSignalsTest {

    @Rule public final MockitoRule rule = MockitoJUnit.rule().strictness(Strictness.STRICT_STUBS);

    @Rule
    public final TestPipeline pipeline = TestPipeline.create();

    @Mock @Bind
    private TradeSignalPublisher signalPublisher;

    @Inject
    private PublishTradeSignals publishTradeSignals;

    @Before
    public void setup() {
        Guice.createInjector(BoundFieldModule.of(this)).injectMembers(this);
    }

    @Test
    public void testPublishTradeSignals_whenSignalIsActionable() {
        // Arrange
        TradeSignal buySignal = TradeSignal.newBuilder().setType(TradeSignal.TradeSignalType.BUY).setPrice(100.0).build();

        PCollection<KV<String, TradeSignal>> input = pipeline.apply(
            Create.of(KV.of("AAPL", buySignal))
        );

        input.apply(publishTradeSignals);

        // Act
        pipeline.run(); // Run the pipeline

        // Assert: Verify that the publisher's publish method was called with the correct signal
        verify(signalPublisher).publish(buySignal);
    }

    @Test
    public void testPublishTradeSignals_whenSignalIsNotActionable() {
        // Arrange
        TradeSignal noneSignal = TradeSignal.newBuilder().setType(TradeSignal.TradeSignalType.NONE).build();

        PCollection<KV<String, TradeSignal>> input = pipeline.apply(
            Create.of(KV.of("AAPL", noneSignal))
        );

        input.apply(publishTradeSignals);

        // Act
        pipeline.run();

        // Assert: Verify that the publisher's publish method was *not* called
        verify(signalPublisher, never()).publish(any());
    }

    @Test
    public void testPublishTradeSignals_logsErrorOnException() {
        // Arrange
        TradeSignal sellSignal = TradeSignal.newBuilder().setType(TradeSignal.TradeSignalType.SELL).setPrice(200.0).build();
        doThrow(new RuntimeException("Publish failed"))
            .when(signalPublisher).publish(sellSignal);

        PCollection<KV<String, TradeSignal>> input = pipeline.apply(
            Create.of(KV.of("GOOGL", sellSignal))
        );

        input.apply(publishTradeSignals);

        // Act and Assert:  Even with the exception, the pipeline should complete.
        // The test will pass as long as it doesn't throw a PipelineExecutionException
        // because of the injected failure in the mock.
        pipeline.run();

        verify(signalPublisher).publish(sellSignal); // Ensure publish was called.
    }
}
