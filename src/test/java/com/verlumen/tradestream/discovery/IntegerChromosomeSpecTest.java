package com.verlumen.tradestream.discovery;

import static com.google.common.truth.Truth.assertThat;

import com.google.common.collect.Range;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;

@RunWith(JUnit4.class)
public class IntegerChromosomeSpecTest {

  @Test
  public void constructor_createsSpecWithRange() {
    Range<Integer> range = Range.closed(5, 50);
    IntegerChromosomeSpec spec = new IntegerChromosomeSpec(range);

    assertThat(spec.getRange()).isEqualTo(range);
  }

  @Test
  public void getRange_returnsSameRangeInstance() {
    Range<Integer> range = Range.closed(10, 100);
    IntegerChromosomeSpec spec = new IntegerChromosomeSpec(range);

    assertThat(spec.getRange()).isSameInstanceAs(range);
  }

  @Test
  public void createChromosome_returnsIntegerChromosome() {
    IntegerChromosomeSpec spec = new IntegerChromosomeSpec(Range.closed(1, 10));
    NumericChromosome<Integer, ?> chromosome = spec.createChromosome();

    assertThat(chromosome).isInstanceOf(IntegerChromosome.class);
  }

  @Test
  public void createChromosome_hasCorrectMinBound() {
    IntegerChromosomeSpec spec = new IntegerChromosomeSpec(Range.closed(5, 100));
    IntegerChromosome chromosome = (IntegerChromosome) spec.createChromosome();

    assertThat(chromosome.min()).isEqualTo(5);
  }

  @Test
  public void createChromosome_hasCorrectMaxBound() {
    IntegerChromosomeSpec spec = new IntegerChromosomeSpec(Range.closed(5, 100));
    IntegerChromosome chromosome = (IntegerChromosome) spec.createChromosome();

    assertThat(chromosome.max()).isEqualTo(100);
  }

  @Test
  public void createChromosome_withSameMinMax_works() {
    IntegerChromosomeSpec spec = new IntegerChromosomeSpec(Range.closed(42, 42));
    IntegerChromosome chromosome = (IntegerChromosome) spec.createChromosome();

    assertThat(chromosome.min()).isEqualTo(42);
    assertThat(chromosome.max()).isEqualTo(42);
  }

  @Test
  public void createChromosome_withNegativeRange_works() {
    IntegerChromosomeSpec spec = new IntegerChromosomeSpec(Range.closed(-100, -10));
    IntegerChromosome chromosome = (IntegerChromosome) spec.createChromosome();

    assertThat(chromosome.min()).isEqualTo(-100);
    assertThat(chromosome.max()).isEqualTo(-10);
  }

  @Test
  public void createChromosome_withRangeSpanningZero_works() {
    IntegerChromosomeSpec spec = new IntegerChromosomeSpec(Range.closed(-50, 50));
    IntegerChromosome chromosome = (IntegerChromosome) spec.createChromosome();

    assertThat(chromosome.min()).isEqualTo(-50);
    assertThat(chromosome.max()).isEqualTo(50);
  }

  @Test
  public void createChromosome_withLargeRange_works() {
    IntegerChromosomeSpec spec = new IntegerChromosomeSpec(Range.closed(0, 1000000));
    IntegerChromosome chromosome = (IntegerChromosome) spec.createChromosome();

    assertThat(chromosome.min()).isEqualTo(0);
    assertThat(chromosome.max()).isEqualTo(1000000);
  }

  @Test
  public void createChromosome_returnsNewInstanceEachTime() {
    IntegerChromosomeSpec spec = new IntegerChromosomeSpec(Range.closed(1, 10));
    NumericChromosome<Integer, ?> c1 = spec.createChromosome();
    NumericChromosome<Integer, ?> c2 = spec.createChromosome();

    assertThat(c1).isNotSameInstanceAs(c2);
  }

  @Test
  public void createChromosome_hasLengthOfOne() {
    IntegerChromosomeSpec spec = new IntegerChromosomeSpec(Range.closed(1, 10));
    IntegerChromosome chromosome = (IntegerChromosome) spec.createChromosome();

    assertThat(chromosome.length()).isEqualTo(1);
  }

  @Test
  public void createChromosome_geneValue_isWithinRange() {
    IntegerChromosomeSpec spec = new IntegerChromosomeSpec(Range.closed(10, 20));
    IntegerChromosome chromosome = (IntegerChromosome) spec.createChromosome();

    int value = chromosome.gene().allele();
    assertThat(value).isAtLeast(10);
    assertThat(value).isAtMost(20);
  }
}
