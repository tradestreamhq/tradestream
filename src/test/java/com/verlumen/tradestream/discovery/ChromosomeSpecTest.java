package com.verlumen.tradestream.discovery;

import static com.google.common.truth.Truth.assertThat;

import com.google.common.collect.Range;
import io.jenetics.DoubleChromosome;
import io.jenetics.DoubleGene;
import io.jenetics.IntegerChromosome;
import io.jenetics.IntegerGene;
import io.jenetics.NumericChromosome;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;

@RunWith(JUnit4.class)
public class ChromosomeSpecTest {

  // ChromosomeSpec.ofInteger tests

  @Test
  public void ofInteger_createsIntegerChromosomeSpec() {
    ChromosomeSpec<Integer> spec = ChromosomeSpec.ofInteger(1, 100);

    assertThat(spec).isInstanceOf(IntegerChromosomeSpec.class);
  }

  @Test
  public void ofInteger_setsCorrectRange() {
    ChromosomeSpec<Integer> spec = ChromosomeSpec.ofInteger(5, 50);

    assertThat(spec.getRange()).isEqualTo(Range.closed(5, 50));
  }

  // ChromosomeSpec.ofDouble tests

  @Test
  public void ofDouble_createsDoubleChromosomeSpec() {
    ChromosomeSpec<Double> spec = ChromosomeSpec.ofDouble(0.0, 1.0);

    assertThat(spec).isInstanceOf(DoubleChromosomeSpec.class);
  }

  @Test
  public void ofDouble_setsCorrectRange() {
    ChromosomeSpec<Double> spec = ChromosomeSpec.ofDouble(0.5, 10.5);

    assertThat(spec.getRange()).isEqualTo(Range.closed(0.5, 10.5));
  }

  // IntegerChromosomeSpec tests

  @Test
  public void integerChromosomeSpec_getRange_returnsClosedRange() {
    ChromosomeSpec<Integer> spec = ChromosomeSpec.ofInteger(10, 20);

    Range<Integer> range = spec.getRange();

    assertThat(range.lowerEndpoint()).isEqualTo(10);
    assertThat(range.upperEndpoint()).isEqualTo(20);
    assertThat(range.contains(10)).isTrue();
    assertThat(range.contains(20)).isTrue();
  }

  @Test
  public void integerChromosomeSpec_createChromosome_returnsIntegerChromosome() {
    ChromosomeSpec<Integer> spec = ChromosomeSpec.ofInteger(1, 100);

    NumericChromosome<Integer, ?> chromosome = spec.createChromosome();

    assertThat(chromosome).isInstanceOf(IntegerChromosome.class);
  }

  @Test
  public void integerChromosomeSpec_createChromosome_hasBoundsMatchingRange() {
    ChromosomeSpec<Integer> spec = ChromosomeSpec.ofInteger(5, 50);

    NumericChromosome<Integer, ?> chromosome = spec.createChromosome();
    IntegerChromosome intChromosome = (IntegerChromosome) chromosome;

    assertThat(intChromosome.min()).isEqualTo(5);
    assertThat(intChromosome.max()).isEqualTo(50);
  }

  @Test
  public void integerChromosomeSpec_chromosomeGeneValues_areWithinRange() {
    int min = 10;
    int max = 100;
    ChromosomeSpec<Integer> spec = ChromosomeSpec.ofInteger(min, max);

    NumericChromosome<Integer, ?> chromosome = spec.createChromosome();

    for (var gene : chromosome) {
      IntegerGene intGene = (IntegerGene) gene;
      assertThat(intGene.intValue()).isAtLeast(min);
      assertThat(intGene.intValue()).isAtMost(max);
    }
  }

  // DoubleChromosomeSpec tests

  @Test
  public void doubleChromosomeSpec_getRange_returnsClosedRange() {
    ChromosomeSpec<Double> spec = ChromosomeSpec.ofDouble(0.1, 0.9);

    Range<Double> range = spec.getRange();

    assertThat(range.lowerEndpoint()).isEqualTo(0.1);
    assertThat(range.upperEndpoint()).isEqualTo(0.9);
    assertThat(range.contains(0.1)).isTrue();
    assertThat(range.contains(0.9)).isTrue();
  }

  @Test
  public void doubleChromosomeSpec_createChromosome_returnsDoubleChromosome() {
    ChromosomeSpec<Double> spec = ChromosomeSpec.ofDouble(0.0, 1.0);

    NumericChromosome<Double, ?> chromosome = spec.createChromosome();

    assertThat(chromosome).isInstanceOf(DoubleChromosome.class);
  }

  @Test
  public void doubleChromosomeSpec_createChromosome_hasBoundsMatchingRange() {
    ChromosomeSpec<Double> spec = ChromosomeSpec.ofDouble(0.5, 10.5);

    NumericChromosome<Double, ?> chromosome = spec.createChromosome();
    DoubleChromosome doubleChromosome = (DoubleChromosome) chromosome;

    assertThat(doubleChromosome.min()).isEqualTo(0.5);
    assertThat(doubleChromosome.max()).isEqualTo(10.5);
  }

  @Test
  public void doubleChromosomeSpec_chromosomeGeneValues_areWithinRange() {
    double min = 0.0;
    double max = 100.0;
    ChromosomeSpec<Double> spec = ChromosomeSpec.ofDouble(min, max);

    NumericChromosome<Double, ?> chromosome = spec.createChromosome();

    for (var gene : chromosome) {
      DoubleGene doubleGene = (DoubleGene) gene;
      assertThat(doubleGene.doubleValue()).isAtLeast(min);
      assertThat(doubleGene.doubleValue()).isAtMost(max);
    }
  }
}
