package com.verlumen.tradestream.backtesting;

import com.google.inject.Inject;
import io.grpc.ManagedChannel;
import io.grpc.ManagedChannelBuilder;

public final class GAServiceClientImpl implements GAServiceClient {
  private final GAServiceGrpc.GAServiceBlockingStub stub;

  @Inject
  GAServiceClientImpl(GAServiceGrpc.GAServiceBlockingStub stub) {
    this.stub = stub;
  }

  @Override
  public BestStrategyResponse requestOptimization(GAOptimizationRequest request) {
    return stub.requestOptimization(request);
  }
}
