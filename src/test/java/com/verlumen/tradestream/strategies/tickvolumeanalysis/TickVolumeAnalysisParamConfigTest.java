package com.verlumen.tradestream.strategies.tickvolumeanalysis;

import static com.google.common.truth.Truth.assertThat;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.TickVolumeAnalysisParameters;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;
import org.junit.Test;

public final class TickVolumeAnalysisParamConfigTest {

  private final TickVolumeAnalysisParamConfig config = new TickVolumeAnalysisParamConfig();

  @Test
  public void getChromosomeSpecs_returnsExpectedSpecs() {
    ImmutableList<?> specs = config.getChromosomeSpecs();
    
    assertThat(specs).hasSize(1);
  }

  @Test
  public void initialChromosomes_returnsExpectedChromosomes() {
    ImmutableList<? extends NumericChromosome<?, ?>> chromosomes = config.initialChromosomes();
    
    assertThat(chromosomes).hasSize(1);
    assertThat(chromosomes.get(0)).isInstanceOf(IntegerChromosome.class);
  }

  @Test
  public void createParameters_withValidChromosomes_returnsValidParameters() 
      throws InvalidProtocolBufferException {
    // Create test chromosome - IntegerChromosome.of(min, max, length) where length is the number of genes
    IntegerChromosome tickPeriodChromosome = IntegerChromosome.of(10, 50, 1);
    
    ImmutableList<NumericChromosome<?, ?>> chromosomes = ImmutableList.of(tickPeriodChromosome);
    
    Any parameters = config.createParameters(chromosomes);
    
    assertThat(parameters.is(TickVolumeAnalysisParameters.class)).isTrue();
    
    TickVolumeAnalysisParameters unpacked = parameters.unpack(TickVolumeAnalysisParameters.class);
    assertThat(unpacked.getTickPeriod()).isAtLeast(10);
    assertThat(unpacked.getTickPeriod()).isAtMost(50);
  }

  @Test
  public void createParameters_withInvalidChromosomes_returnsDefaultParameters() 
      throws InvalidProtocolBufferException {
    ImmutableList<NumericChromosome<?, ?>> chromosomes = ImmutableList.of();
    
    Any parameters = config.createParameters(chromosomes);
    
    assertThat(parameters.is(TickVolumeAnalysisParameters.class)).isTrue();
    
    TickVolumeAnalysisParameters unpacked = parameters.unpack(TickVolumeAnalysisParameters.class);
    assertThat(unpacked.getTickPeriod()).isEqualTo(20);
  }
} 