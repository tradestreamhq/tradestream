package com.verlumen.tradestream.signals;

import static org.junit.Assert.*;
import static org.mockito.Mockito.*;

import com.google.common.collect.ImmutableList;
import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import com.verlumen.tradestream.marketdata.Candle;
import com.verlumen.tradestream.strategies.StrategyState;
import com.verlumen.tradestream.ta4j.Ta4jModule;
import org.apache.beam.sdk.transforms.DoFn;
import org.apache.beam.sdk.transforms.ParDo;
import org.apache.beam.sdk.values.KV;
import org.apache.beam.sdk.values.PCollection;
import org.apache.beam.sdk.testing.TestPipeline;
import org.apache.beam.sdk.testing.PAssert;
import org.apache.beam.sdk.transforms.Create;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.mockito.Mock;
import org.mockito.junit.MockitoJUnit;
import org.mockito.junit.MockitoRule;
import org.mockito.quality.Strictness;
import org.mockito.junit.MockitoJUnitRunner;
import org.ta4j.core.BarSeries;
import org.ta4j.core.Strategy;

@RunWith(MockitoJUnitRunner.class)
public class GenerateTradeSignalsTest {
    
    @Rule
    public final MockitoRule rule = MockitoJUnit.rule().strictness(Strictness.STRICT_STUBS);
    
    @Rule
    public final TestPipeline pipeline = TestPipeline.create();
    
    @Mock private StrategyState mockStrategyState;
    @Mock private Strategy mockTa4jStrategy;
    @Mock private BarSeries mockBarSeries;
    
    @Inject private GenerateTradeSignals.GenerateSignalsDoFn generateSignalsDoFn;
    
    @Before
    public void setUp() {
        Guice.createInjector(
            BoundFieldModule.of(this),
            Ta4jModule.create()).injectMembers(this);
    }
    
    @Test
    public void testGenerateBuySignal() throws Exception {
        when(mockStrategyState.getCurrentStrategy(any(BarSeries.class))).thenReturn(mockTa4jStrategy);
        when(mockTa4jStrategy.shouldEnter(anyInt())).thenReturn(true);
        when(mockTa4jStrategy.shouldExit(anyInt())).thenReturn(false);
        
        Candle candle = mock(Candle.class);
        when(candle.getClose()).thenReturn(100.0);
        when(mockBarSeries.getEndIndex()).thenReturn(10);
        
        KV<String, StrategyState> input = KV.of("test-key", mockStrategyState);
        PCollection<KV<String, StrategyState>> inputCollection = pipeline.apply(Create.of(input));
        PCollection<KV<String, TradeSignal>> outputCollection = inputCollection.apply(ParDo.of(generateSignalsDoFn));
        
        PAssert.that(outputCollection).satisfies(output -> {
            KV<String, TradeSignal> result = output.iterator().next();
            assertEquals("test-key", result.getKey());
            assertEquals(TradeSignal.TradeSignalType.BUY, result.getValue().getType());
            return null;
        });
        
        pipeline.run();
    }
}
