package com.verlumen.tradestream.backtesting;

import com.google.inject.AbstractModule;
import com.google.inject.Provides;
import com.google.inject.Singleton;
import io.grpc.ManagedChannel;
import io.grpc.ManagedChannelBuilder;

public final class BacktestingModule extends AbstractModule {
  private static final String DEFAULT_BACKTEST_SERVICE_HOST = "backtest-service";
  private static final int DEFAULT_BACKTEST_SERVICE_PORT = 50051;
  private static final String DEFAULT_GA_SERVICE_HOST = "ga-service";
  private static final int DEFAULT_GA_SERVICE_PORT = 50052;

  public static BacktestingModule create() {
    return new BacktestingModule();
  }

  @Override
  protected void configure() {
    bind(GAServiceClient.class).to(GAServiceClientImpl.class);
  }

  @Provides 
  @Singleton
  BacktestServiceGrpc.BacktestServiceBlockingStub provideBacktestServiceStub() {
    ManagedChannel channel = ManagedChannelBuilder.forAddress(
            DEFAULT_BACKTEST_SERVICE_HOST, 
            DEFAULT_BACKTEST_SERVICE_PORT)
        .usePlaintext()
        .build();
    return BacktestServiceGrpc.newBlockingStub(channel);
  }

  @Provides
  @Singleton
  GAServiceGrpc.GAServiceBlockingStub provideGAServiceStub() {
    ManagedChannel channel = ManagedChannelBuilder.forAddress(
            DEFAULT_GA_SERVICE_HOST, 
            DEFAULT_GA_SERVICE_PORT)
        .usePlaintext()
        .build();
    return GAServiceGrpc.newBlockingStub(channel);
  }

  private BacktestingModule() {}
}
