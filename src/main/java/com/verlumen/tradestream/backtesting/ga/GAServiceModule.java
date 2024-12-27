package com.verlumen.tradestream.backtesting.ga;

import com.google.inject.AbstractModule;
import com.verlumen.tradestream.backtesting.BacktestRunner;
import io.jenetics.Engine;
import io.jenetics.Genotype;
import io.jenetics.IntegerGene;

/**
 * Wires up GA-related classes in the Guice DI context.
 */
public final class GAServiceModule extends AbstractModule {
  @Override
  protected void configure() {
    // Bind the GAService implementation
    bind(GAServiceImpl.class).asEagerSingleton();
    // We might bind an Engine<...> here if we want a single GA engine for all strategies, etc.
  }
}
