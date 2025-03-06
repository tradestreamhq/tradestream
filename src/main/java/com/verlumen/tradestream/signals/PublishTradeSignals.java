package com.verlumen.tradestream.pipeline.strategies;

import com.google.common.flogger.FluentLogger;
import com.google.inject.Inject;
import org.apache.beam.sdk.transforms.DoFn;
import org.apache.beam.sdk.transforms.ParDo;
import org.apache.beam.sdk.transforms.PTransform;
import org.apache.beam.sdk.values.KV;
import org.apache.beam.sdk.values.PCollection;
import org.apache.beam.sdk.values.PDone;

/**
 * Publishes trade signals using the TradeSignalPublisher service.
 */
public class PublishTradeSignals extends PTransform<PCollection<KV<String, TradeSignal>>, PDone> {

  private static final FluentLogger logger = FluentLogger.forEnclosingClass();
  
  private final TradeSignalPublisher signalPublisher;
  
  @Inject
  public PublishTradeSignals(TradeSignalPublisher signalPublisher) {
    this.signalPublisher = signalPublisher;
  }
  
  @Override
  public PDone expand(PCollection<KV<String, TradeSignal>> input) {
    input.apply("PublishSignals", ParDo.of(new PublishSignalsDoFn(signalPublisher)));
    return PDone.in(input.getPipeline());
  }
  
  /**
   * DoFn that publishes trade signals but only if they are actionable (BUY or SELL).
   */
  private static class PublishSignalsDoFn extends DoFn<KV<String, TradeSignal>, Void> {
    
    private final TradeSignalPublisher signalPublisher;
    
    PublishSignalsDoFn(TradeSignalPublisher signalPublisher) {
      this.signalPublisher = signalPublisher;
    }
    
    @ProcessElement
    public void processElement(ProcessContext context) {
      KV<String, TradeSignal> element = context.element();
      String key = element.getKey();
      TradeSignal signal = element.getValue();
      
      // Only publish actionable signals
      if (signal.getType() != TradeSignal.TradeSignalType.NONE) {
        try {
          logger.atInfo().log("Publishing %s signal for %s at price %f", 
              signal.getType(), key, signal.getPrice());
          signalPublisher.publish(signal);
        } catch (Exception e) {
          logger.atSevere().withCause(e).log(
              "Error publishing signal for %s: %s", key, e.getMessage());
        }
      }
    }
  }
}
