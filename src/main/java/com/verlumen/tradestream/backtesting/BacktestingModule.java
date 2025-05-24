package com.verlumen.tradestream.backtesting;

import com.google.common.collect.ImmutableList;
import com.google.inject.AbstractModule;
import com.google.inject.TypeLiteral;

public final class BacktestingModule extends AbstractModule {
  public static BacktestingModule create() {
    return new BacktestingModule();
  }

  @Override
  protected void configure() {
    bind(BacktestRequestFactory.class).to(BacktestRequestFactoryImpl.class);
    bind(BacktestRunner.class).to(BacktestRunnerImpl.class);
    bind(FitnessCalculator.class).to(FitnessCalculatorImpl.class);
    bind(GAEngineFactory.class).to(GAEngineFactoryImpl.class);
    bind(GeneticAlgorithmOrchestrator.class).to(GeneticAlgorithmOrchestratorImpl.class);
    bind(GenotypeConverter.class).to(GenotypeConverterImpl.class);
    bind(new TypeLiteral<ImmutableList<ParamConfig>>() {}).toInstance(ParamConfigs.ALL_CONFIGS);
    bind(ParamConfigManager.class).to(ParamConfigManagerImpl.class);
  }
}
