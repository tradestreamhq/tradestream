package com.verlumen.tradestream.discovery;

import static com.google.common.truth.Truth.assertThat;

import com.google.common.collect.Range;
import io.jenetics.DoubleChromosome;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;

@RunWith(JUnit4.class)
public class ChromosomeSpecTest {

  @Test
  public void ofInteger_createsSpecWithCorrectRange() {
    ChromosomeSpec<Integer> spec = ChromosomeSpec.ofInteger(5, 50);
    Range<Integer> range = spec.getRange();

    assertThat(range.lowerEndpoint()).isEqualTo(5);
    assertThat(range.upperEndpoint()).isEqualTo(50);
  }

  @Test
  public void ofInteger_createChromosome_returnsIntegerChromosome() {
    ChromosomeSpec<Integer> spec = ChromosomeSpec.ofInteger(10, 100);
    NumericChromosome<Integer, ?> chromosome = spec.createChromosome();

    assertThat(chromosome).isInstanceOf(IntegerChromosome.class);
  }

  @Test
  public void ofInteger_createChromosome_hasCorrectBounds() {
    ChromosomeSpec<Integer> spec = ChromosomeSpec.ofInteger(1, 10);
    IntegerChromosome chromosome = (IntegerChromosome) spec.createChromosome();

    assertThat(chromosome.min()).isEqualTo(1);
    assertThat(chromosome.max()).isEqualTo(10);
  }

  @Test
  public void ofDouble_createsSpecWithCorrectRange() {
    ChromosomeSpec<Double> spec = ChromosomeSpec.ofDouble(0.1, 0.9);
    Range<Double> range = spec.getRange();

    assertThat(range.lowerEndpoint()).isWithin(0.001).of(0.1);
    assertThat(range.upperEndpoint()).isWithin(0.001).of(0.9);
  }

  @Test
  public void ofDouble_createChromosome_returnsDoubleChromosome() {
    ChromosomeSpec<Double> spec = ChromosomeSpec.ofDouble(0.0, 1.0);
    NumericChromosome<Double, ?> chromosome = spec.createChromosome();

    assertThat(chromosome).isInstanceOf(DoubleChromosome.class);
  }

  @Test
  public void ofDouble_createChromosome_hasCorrectBounds() {
    ChromosomeSpec<Double> spec = ChromosomeSpec.ofDouble(0.5, 2.5);
    DoubleChromosome chromosome = (DoubleChromosome) spec.createChromosome();

    assertThat(chromosome.min()).isWithin(0.001).of(0.5);
    assertThat(chromosome.max()).isWithin(0.001).of(2.5);
  }

  @Test
  public void ofInteger_sameMinMax_works() {
    ChromosomeSpec<Integer> spec = ChromosomeSpec.ofInteger(5, 5);
    Range<Integer> range = spec.getRange();

    assertThat(range.lowerEndpoint()).isEqualTo(5);
    assertThat(range.upperEndpoint()).isEqualTo(5);
  }

  @Test
  public void ofDouble_sameMinMax_works() {
    ChromosomeSpec<Double> spec = ChromosomeSpec.ofDouble(1.5, 1.5);
    Range<Double> range = spec.getRange();

    assertThat(range.lowerEndpoint()).isWithin(0.001).of(1.5);
    assertThat(range.upperEndpoint()).isWithin(0.001).of(1.5);
  }

  @Test
  public void ofInteger_negativeRange_works() {
    ChromosomeSpec<Integer> spec = ChromosomeSpec.ofInteger(-100, -10);
    Range<Integer> range = spec.getRange();

    assertThat(range.lowerEndpoint()).isEqualTo(-100);
    assertThat(range.upperEndpoint()).isEqualTo(-10);
  }

  @Test
  public void ofDouble_negativeRange_works() {
    ChromosomeSpec<Double> spec = ChromosomeSpec.ofDouble(-1.0, -0.1);
    Range<Double> range = spec.getRange();

    assertThat(range.lowerEndpoint()).isWithin(0.001).of(-1.0);
    assertThat(range.upperEndpoint()).isWithin(0.001).of(-0.1);
  }

  @Test
  public void ofInteger_largeRange_works() {
    ChromosomeSpec<Integer> spec = ChromosomeSpec.ofInteger(0, 1000000);
    IntegerChromosome chromosome = (IntegerChromosome) spec.createChromosome();

    assertThat(chromosome.min()).isEqualTo(0);
    assertThat(chromosome.max()).isEqualTo(1000000);
  }

  @Test
  public void ofDouble_smallRange_works() {
    ChromosomeSpec<Double> spec = ChromosomeSpec.ofDouble(0.001, 0.002);
    DoubleChromosome chromosome = (DoubleChromosome) spec.createChromosome();

    assertThat(chromosome.min()).isWithin(0.0001).of(0.001);
    assertThat(chromosome.max()).isWithin(0.0001).of(0.002);
  }

  @Test
  public void createChromosome_returnsNewInstance() {
    ChromosomeSpec<Integer> spec = ChromosomeSpec.ofInteger(1, 10);
    NumericChromosome<Integer, ?> c1 = spec.createChromosome();
    NumericChromosome<Integer, ?> c2 = spec.createChromosome();

    // Different instances
    assertThat(c1).isNotSameInstanceAs(c2);
  }
}
