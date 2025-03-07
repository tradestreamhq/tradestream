package com.verlumen.tradestream.signals;

import static org.junit.Assert.*;

import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.testing.fieldbinder.Bind;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import java.io.Serializable;
import java.util.ArrayList;
import java.util.List;
import org.apache.beam.sdk.testing.TestPipeline;
import org.apache.beam.sdk.transforms.Create;
import org.apache.beam.sdk.values.KV;
import org.apache.beam.sdk.values.PCollection;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;

@RunWith(JUnit4.class)
public class PublishTradeSignalsTest {

    @Rule 
    public final TestPipeline pipeline = TestPipeline.create();

    // Bind a fake implementation of TradeSignalPublisher as a static inner class.
    @Bind
    private FakeTradeSignalPublisher fakeSignalPublisher = new FakeTradeSignalPublisher();

    @Inject
    private PublishTradeSignals publishTradeSignals;

    @Before
    public void setup() {
        Guice.createInjector(BoundFieldModule.of(this)).injectMembers(this);
    }

    @Test
    public void testPublishTradeSignals_whenSignalIsActionable() {
        // Arrange
        TradeSignal buySignal = TradeSignal.newBuilder()
                .setType(TradeSignal.TradeSignalType.BUY)
                .setPrice(100.0)
                .build();

        PCollection<KV<String, TradeSignal>> input = pipeline.apply(
            Create.of(KV.of("AAPL", buySignal))
        );

        input.apply(publishTradeSignals);

        // Act
        pipeline.run();

        // Assert: Verify that the fake publisher recorded the published signal.
        List<TradeSignal> publishedSignals = fakeSignalPublisher.getPublishedSignals();
        assertEquals(1, publishedSignals.size());
        assertEquals(buySignal, publishedSignals.get(0));
    }

    @Test
    public void testPublishTradeSignals_whenSignalIsNotActionable() {
        // Arrange
        TradeSignal noneSignal = TradeSignal.newBuilder()
                .setType(TradeSignal.TradeSignalType.NONE)
                .build();

        PCollection<KV<String, TradeSignal>> input = pipeline.apply(
            Create.of(KV.of("AAPL", noneSignal))
        );

        input.apply(publishTradeSignals);

        // Act
        pipeline.run();

        // Assert: No signals should be published.
        List<TradeSignal> publishedSignals = fakeSignalPublisher.getPublishedSignals();
        assertTrue(publishedSignals.isEmpty());
    }

    @Test
    public void testPublishTradeSignals_logsErrorOnException() {
        // Arrange
        // Configure the fake to throw an exception after recording the signal.
        fakeSignalPublisher.setThrowException(true);

        TradeSignal sellSignal = TradeSignal.newBuilder()
                .setType(TradeSignal.TradeSignalType.SELL)
                .setPrice(200.0)
                .build();

        PCollection<KV<String, TradeSignal>> input = pipeline.apply(
            Create.of(KV.of("GOOGL", sellSignal))
        );

        input.apply(publishTradeSignals);

        // Act & Assert: The pipeline should complete even if an exception is thrown.
        pipeline.run();

        // Verify that the fake recorded the attempted publish.
        List<TradeSignal> publishedSignals = fakeSignalPublisher.getPublishedSignals();
        assertEquals(1, publishedSignals.size());
        assertEquals(sellSignal, publishedSignals.get(0));
    }

    /**
     * A fake implementation of TradeSignalPublisher for testing purposes.
     * This fake records the signals that were published and can optionally throw an exception.
     */
    public static class FakeTradeSignalPublisher implements TradeSignalPublisher, Serializable {
        private static final long serialVersionUID = 1L;
        private final List<TradeSignal> publishedSignals = new ArrayList<>();
        private boolean throwException = false;

        public void setThrowException(boolean throwException) {
            this.throwException = throwException;
        }

        @Override
        public void publish(TradeSignal signal) {
            publishedSignals.add(signal);
            if (throwException) {
                throw new RuntimeException("Publish failed");
            }
        }

        public List<TradeSignal> getPublishedSignals() {
            return publishedSignals;
        }
    }
}
