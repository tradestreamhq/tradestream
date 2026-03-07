package com.verlumen.tradestream.discovery;

import static com.google.common.truth.Truth.assertThat;
import static org.junit.Assert.assertThrows;

import java.lang.reflect.Constructor;
import java.lang.reflect.InvocationTargetException;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;

@RunWith(JUnit4.class)
public class GAConstantsTest {

  @Test
  public void crossoverProbability_isWithinValidRange() {
    assertThat(GAConstants.CROSSOVER_PROBABILITY).isAtLeast(0.0);
    assertThat(GAConstants.CROSSOVER_PROBABILITY).isAtMost(1.0);
  }

  @Test
  public void crossoverProbability_hasExpectedValue() {
    assertThat(GAConstants.CROSSOVER_PROBABILITY).isWithin(0.001).of(0.35);
  }

  @Test
  public void defaultPopulationSize_isPositive() {
    assertThat(GAConstants.DEFAULT_POPULATION_SIZE).isGreaterThan(0);
  }

  @Test
  public void defaultPopulationSize_hasExpectedValue() {
    assertThat(GAConstants.DEFAULT_POPULATION_SIZE).isEqualTo(50);
  }

  @Test
  public void defaultMaxGenerations_isPositive() {
    assertThat(GAConstants.DEFAULT_MAX_GENERATIONS).isGreaterThan(0);
  }

  @Test
  public void defaultMaxGenerations_hasExpectedValue() {
    assertThat(GAConstants.DEFAULT_MAX_GENERATIONS).isEqualTo(100);
  }

  @Test
  public void mutationProbability_isWithinValidRange() {
    assertThat(GAConstants.MUTATION_PROBABILITY).isAtLeast(0.0);
    assertThat(GAConstants.MUTATION_PROBABILITY).isAtMost(1.0);
  }

  @Test
  public void mutationProbability_hasExpectedValue() {
    assertThat(GAConstants.MUTATION_PROBABILITY).isWithin(0.001).of(0.15);
  }

  @Test
  public void tournamentSize_isPositive() {
    assertThat(GAConstants.TOURNAMENT_SIZE).isGreaterThan(0);
  }

  @Test
  public void tournamentSize_hasExpectedValue() {
    assertThat(GAConstants.TOURNAMENT_SIZE).isEqualTo(3);
  }

  @Test
  public void tournamentSize_isLessThanPopulationSize() {
    assertThat(GAConstants.TOURNAMENT_SIZE).isLessThan(GAConstants.DEFAULT_POPULATION_SIZE);
  }

  @Test
  public void crossoverProbability_plusMutationProbability_isLessThanOrEqualToOne() {
    double totalProbability =
        GAConstants.CROSSOVER_PROBABILITY + GAConstants.MUTATION_PROBABILITY;
    assertThat(totalProbability).isAtMost(1.0);
  }

  @Test
  public void populationSize_isSufficientForTournamentSelection() {
    // Tournament selection requires population >= tournament size
    assertThat(GAConstants.DEFAULT_POPULATION_SIZE).isAtLeast(GAConstants.TOURNAMENT_SIZE);
  }

  @Test
  public void maxGenerations_isReasonableForConvergence() {
    // Max generations should be sufficient for algorithm convergence
    assertThat(GAConstants.DEFAULT_MAX_GENERATIONS).isAtLeast(10);
    assertThat(GAConstants.DEFAULT_MAX_GENERATIONS).isAtMost(10000);
  }
}
