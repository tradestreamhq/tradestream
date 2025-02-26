package com.verlumen.tradestream.backtesting;

import com.google.auto.value.AutoValue;
import com.google.inject.AbstractModule;
import com.google.inject.Provides;
import com.google.inject.Singleton;

public abstract class BacktestingModule extends AbstractModule {
  public static BacktestingModule create() {
    return new BacktestingModule();
  }

  @Override
  protected void configure() {
    install(GenotypeConverterModule.create());
  }

  @AutoValue
  abstract static class GenotypeConverterModule extends AbstractModule  
    public static BacktestingModule create() {
      return new AutoValue_BacktestingModule_GenotypeConverterModule();
    }

    @Override
    protected void configure() {
      bind(GenotypeConverter.class).to(GenotypeConverterImpl.class); 
    } 
  }
}
