package com.verlumen.tradestream.signals;

import static org.mockito.Mockito.*;

import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import org.apache.beam.sdk.testing.TestPipeline;
import org.apache.beam.sdk.testing.PAssert;
import org.apache.beam.sdk.transforms.Create;
import org.apache.beam.sdk.values.KV;
import org.apache.beam.sdk.values.PCollection;
import org.apache.beam.sdk.values.PDone;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.mockito.Mock;
import org.mockito.junit.MockitoJUnit;
import org.mockito.junit.MockitoRule;
import org.mockito.quality.Strictness;

import java.util.Arrays;

@RunWith(org.mockito.junit.MockitoJUnitRunner.class)
public class PublishTradeSignalsTest {
    
    @Rule public final MockitoRule rule = MockitoJUnit.rule().strictness(Strictness.STRICT_STUBS);
    @Rule public final TestPipeline pipeline = TestPipeline.create();
    
    @Mock private TradeSignalPublisher signalPublisher;
    
    @Inject private PublishTradeSignals publishTradeSignals;
    
    @Before
    public void setup() {
        Guice.createInjector(BoundFieldModule.of(this)).injectMembers(this);
    }
    
    @Test
    public void testPublishTradeSignals_whenSignalIsActionable() {
        TradeSignal buySignal = mock(TradeSignal.class);
        when(buySignal.getType()).thenReturn(TradeSignal.TradeSignalType.BUY);
        when(buySignal.getPrice()).thenReturn(100.0);

        PCollection<KV<String, TradeSignal>> input = pipeline.apply(
            Create.of(KV.of("AAPL", buySignal))
        );
        
        PDone result = input.apply(publishTradeSignals);
        
        PAssert.that(result).isNotNull();
        pipeline.run();

        verify(signalPublisher).publish(buySignal);
    }
    
    @Test
    public void testPublishTradeSignals_whenSignalIsNotActionable() {
        TradeSignal noneSignal = mock(TradeSignal.class);
        when(noneSignal.getType()).thenReturn(TradeSignal.TradeSignalType.NONE);
        
        PCollection<KV<String, TradeSignal>> input = pipeline.apply(
            Create.of(KV.of("AAPL", noneSignal))
        );
        
        PDone result = input.apply(publishTradeSignals);
        
        PAssert.that(result).isNotNull();
        pipeline.run();

        verify(signalPublisher, never()).publish(any());
    }
    
    @Test
    public void testPublishTradeSignals_logsErrorOnException() {
        TradeSignal sellSignal = mock(TradeSignal.class);
        when(sellSignal.getType()).thenReturn(TradeSignal.TradeSignalType.SELL);
        when(sellSignal.getPrice()).thenReturn(200.0);
        doThrow(new RuntimeException("Publish failed"))
            .when(signalPublisher).publish(sellSignal);
        
        PCollection<KV<String, TradeSignal>> input = pipeline.apply(
            Create.of(KV.of("GOOGL", sellSignal))
        );
        
        PDone result = input.apply(publishTradeSignals);
        
        PAssert.that(result).isNotNull();
        pipeline.run();

        verify(signalPublisher).publish(sellSignal);
    }
}
