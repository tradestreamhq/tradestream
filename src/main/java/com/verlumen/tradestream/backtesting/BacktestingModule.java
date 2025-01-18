package com.verlumen.tradestream.backtesting;

import com.google.inject.AbstractModule;
import com.google.inject.Provides;
import com.google.inject.Singleton;
import com.verlumen.tradestream.grpc.Endpoint;

public final class BacktestingModule extends AbstractModule {
  private static final String DEFAULT_BACKTEST_SERVICE_HOST = "backtest-service";
  private static final int DEFAULT_BACKTEST_SERVICE_PORT = 50051;
  private static final String DEFAULT_GA_SERVICE_HOST = "ga-service";
  private static final int DEFAULT_GA_SERVICE_PORT = 50052;

  public static BacktestingModule create() {
    return new BacktestingModule(
      new Endpoint(DEFAULT_BACKTEST_SERVICE_HOST, DEFAULT_BACKTEST_SERVICE_PORT),
      new Endpoint(DEFAULT_GA_SERVICE_HOST, DEFAULT_GA_SERVICE_PORT));
  }

  private final Endpoint backtestEndpoint;
  private final Endpoint gaEndpoint;

  BacktestingModule(Endpoint backtestEndpoint, Endpoint gaEndpoint) {
    this.backtestEndpoint = backtestEndpoint;
    this.gaEndpoint = gaEndpoint;
  }

  @Override
  protected void configure() {
    bind(BacktestServiceClient.class).to(BacktestServiceClientImpl.class);
    bind(GAServiceClient.class).to(GAServiceClientImpl.class);
  }

  @Provides 
  @Singleton
  BacktestServiceGrpc.BacktestServiceBlockingStub provideBacktestServiceStub() {
    return BacktestServiceGrpc.newBlockingStub(backtestEndpoint.createChannel());
  }

  @Provides
  @Singleton
  GAServiceGrpc.GAServiceBlockingStub provideGAServiceStub() {
    return GAServiceGrpc.newBlockingStub(gaEndpoint.createChannel());
  }
}
