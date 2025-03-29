package com.verlumen.tradestream.backtesting;

/**
 * Constants used throughout the genetic algorithm optimization process.
 * Extracted to a separate class to avoid duplication and facilitate changes.
 */
final class GAConstants {
  static final double CROSSOVER_PROBABILITY = 0.35;
  static final int DEFAULT_POPULATION_SIZE = 50;
  static final int DEFAULT_MAX_GENERATIONS = 100;
  static final double MUTATION_PROBABILITY = 0.15;
  static final int TOURNAMENT_SIZE = 3;

  private GAConstants() {}
}
