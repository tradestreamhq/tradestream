package com.verlumen.tradestream.backtesting;

import com.google.inject.AbstractModule;
import com.google.inject.Provides;
import com.google.inject.Singleton;

public final class BacktestingModule extends AbstractModule {
  public static BacktestingModule create() {
    return new BacktestingModule();
  }

  @Override
  protected void configure() {
    bind(BacktestRunner.class).to(BacktestRunnerImpl.class);
    bind(FitnessCalculator.class).to(FitnessCalculatorImpl.class);
    bind(GAEngineFactory.class).to(GAEngineFactoryImpl.class);
    bind(GeneticAlgorithmOrchestrator.class).to(GeneticAlgorithmOrchestratorImpl.class);
    bind(GenotypeConverter.class).to(GenotypeConverterImpl.class);
    bind(ParamConfigManager.class).to(ParamConfigManagerImpl.class);
  }
}
