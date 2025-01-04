package com.verlumen.tradestream.backtesting;

import com.google.inject.AbstractModule;

public final class BacktestingModule extends AbstractModule {
  static BacktestingModule create() {
    return new BacktestingModule();
  }

  @Override
  protected void configure() {
    bind(GAServiceClient.class).to(GAServiceClientImpl.class);
  }

  private BacktestingModule() {}
}
