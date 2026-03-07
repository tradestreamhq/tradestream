package com.verlumen.tradestream.discovery;

import static com.google.common.truth.Truth.assertThat;

import com.google.common.collect.Range;
import io.jenetics.DoubleChromosome;
import io.jenetics.NumericChromosome;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;

@RunWith(JUnit4.class)
public class DoubleChromosomeSpecTest {

  @Test
  public void constructor_createsSpecWithRange() {
    Range<Double> range = Range.closed(0.1, 0.9);
    DoubleChromosomeSpec spec = new DoubleChromosomeSpec(range);

    assertThat(spec.getRange()).isEqualTo(range);
  }

  @Test
  public void getRange_returnsSameRangeInstance() {
    Range<Double> range = Range.closed(0.0, 1.0);
    DoubleChromosomeSpec spec = new DoubleChromosomeSpec(range);

    assertThat(spec.getRange()).isSameInstanceAs(range);
  }

  @Test
  public void createChromosome_returnsDoubleChromosome() {
    DoubleChromosomeSpec spec = new DoubleChromosomeSpec(Range.closed(0.0, 1.0));
    NumericChromosome<Double, ?> chromosome = spec.createChromosome();

    assertThat(chromosome).isInstanceOf(DoubleChromosome.class);
  }

  @Test
  public void createChromosome_hasCorrectMinBound() {
    DoubleChromosomeSpec spec = new DoubleChromosomeSpec(Range.closed(0.5, 2.5));
    DoubleChromosome chromosome = (DoubleChromosome) spec.createChromosome();

    assertThat(chromosome.min()).isWithin(0.0001).of(0.5);
  }

  @Test
  public void createChromosome_hasCorrectMaxBound() {
    DoubleChromosomeSpec spec = new DoubleChromosomeSpec(Range.closed(0.5, 2.5));
    DoubleChromosome chromosome = (DoubleChromosome) spec.createChromosome();

    assertThat(chromosome.max()).isWithin(0.0001).of(2.5);
  }

  @Test
  public void createChromosome_withSameMinMax_works() {
    DoubleChromosomeSpec spec = new DoubleChromosomeSpec(Range.closed(1.5, 1.5));
    DoubleChromosome chromosome = (DoubleChromosome) spec.createChromosome();

    assertThat(chromosome.min()).isWithin(0.0001).of(1.5);
    assertThat(chromosome.max()).isWithin(0.0001).of(1.5);
  }

  @Test
  public void createChromosome_withNegativeRange_works() {
    DoubleChromosomeSpec spec = new DoubleChromosomeSpec(Range.closed(-1.0, -0.1));
    DoubleChromosome chromosome = (DoubleChromosome) spec.createChromosome();

    assertThat(chromosome.min()).isWithin(0.0001).of(-1.0);
    assertThat(chromosome.max()).isWithin(0.0001).of(-0.1);
  }

  @Test
  public void createChromosome_withRangeSpanningZero_works() {
    DoubleChromosomeSpec spec = new DoubleChromosomeSpec(Range.closed(-0.5, 0.5));
    DoubleChromosome chromosome = (DoubleChromosome) spec.createChromosome();

    assertThat(chromosome.min()).isWithin(0.0001).of(-0.5);
    assertThat(chromosome.max()).isWithin(0.0001).of(0.5);
  }

  @Test
  public void createChromosome_withSmallRange_works() {
    DoubleChromosomeSpec spec = new DoubleChromosomeSpec(Range.closed(0.001, 0.002));
    DoubleChromosome chromosome = (DoubleChromosome) spec.createChromosome();

    assertThat(chromosome.min()).isWithin(0.0001).of(0.001);
    assertThat(chromosome.max()).isWithin(0.0001).of(0.002);
  }

  @Test
  public void createChromosome_withLargeRange_works() {
    DoubleChromosomeSpec spec = new DoubleChromosomeSpec(Range.closed(0.0, 1000.0));
    DoubleChromosome chromosome = (DoubleChromosome) spec.createChromosome();

    assertThat(chromosome.min()).isWithin(0.0001).of(0.0);
    assertThat(chromosome.max()).isWithin(0.0001).of(1000.0);
  }

  @Test
  public void createChromosome_returnsNewInstanceEachTime() {
    DoubleChromosomeSpec spec = new DoubleChromosomeSpec(Range.closed(0.0, 1.0));
    NumericChromosome<Double, ?> c1 = spec.createChromosome();
    NumericChromosome<Double, ?> c2 = spec.createChromosome();

    assertThat(c1).isNotSameInstanceAs(c2);
  }

  @Test
  public void createChromosome_hasLengthOfOne() {
    DoubleChromosomeSpec spec = new DoubleChromosomeSpec(Range.closed(0.0, 1.0));
    DoubleChromosome chromosome = (DoubleChromosome) spec.createChromosome();

    assertThat(chromosome.length()).isEqualTo(1);
  }

  @Test
  public void createChromosome_geneValue_isWithinRange() {
    DoubleChromosomeSpec spec = new DoubleChromosomeSpec(Range.closed(0.25, 0.75));
    DoubleChromosome chromosome = (DoubleChromosome) spec.createChromosome();

    double value = chromosome.gene().allele();
    assertThat(value).isAtLeast(0.25);
    assertThat(value).isAtMost(0.75);
  }

  @Test
  public void createChromosome_withPreciseValues_maintainsPrecision() {
    DoubleChromosomeSpec spec = new DoubleChromosomeSpec(Range.closed(0.123456789, 0.987654321));
    DoubleChromosome chromosome = (DoubleChromosome) spec.createChromosome();

    assertThat(chromosome.min()).isWithin(1e-9).of(0.123456789);
    assertThat(chromosome.max()).isWithin(1e-9).of(0.987654321);
  }
}
