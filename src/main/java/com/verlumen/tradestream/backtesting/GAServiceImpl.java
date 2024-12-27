package com.verlumen.tradestream.backtesting;

import com.google.inject.Inject;
import io.grpc.Status;
import io.grpc.stub.StreamObserver;
import java.util.logging.Logger;

/**
 * Implementation that orchestrates a GA. 
 * Under the hood, calls BacktestService repeatedly with different 'Any' parameters.
 */
public final class GAServiceImpl extends GAServiceGrpc.GAServiceImplBase {
  private static final Logger logger = Logger.getLogger(GAServiceImpl.class.getName());

  private final GeneticAlgorithmOrchestrator gaOrchestrator;

  @Inject
  public GAServiceImpl(GeneticAlgorithmOrchestrator gaOrchestrator) {
    this.gaOrchestrator = gaOrchestrator;
  }

  @Override
  public void requestOptimization(GAOptimizationRequest request,
      StreamObserver<BestStrategyResponse> responseObserver) {
    try {
      BestStrategyResponse best = gaOrchestrator.runOptimization(request);
      responseObserver.onNext(best);
      responseObserver.onCompleted();
    } catch (Exception e) {
      logger.severe("Error in requestOptimization: " + e.getMessage());
      responseObserver.onError(Status.INTERNAL
          .withCause(e)
          .withDescription(e.getMessage())
          .asRuntimeException());
    }
  }
}
