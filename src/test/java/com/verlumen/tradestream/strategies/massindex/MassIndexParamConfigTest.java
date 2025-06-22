package com.verlumen.tradestream.strategies.massindex;

import static com.google.common.truth.Truth.assertThat;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.protos.strategies.MassIndexParameters;
import com.verlumen.tradestream.protos.strategies.Strategy;
import io.jenetics.NumericChromosome;
import org.junit.Test;

public final class MassIndexParamConfigTest {
  private final MassIndexParamConfig config = new MassIndexParamConfig();

  @Test
  public void getChromosomeSpecs_returnsExpectedSpecs() {
    assertThat(config.getChromosomeSpecs()).hasSize(2);
  }

  @Test
  public void initialChromosomes_returnsExpectedChromosomes() {
    ImmutableList<? extends NumericChromosome<?, ?>> chromosomes = config.initialChromosomes();
    assertThat(chromosomes).hasSize(2);
  }

  @Test
  public void createParameters_returnsValidParameters() throws InvalidProtocolBufferException {
    ImmutableList<? extends NumericChromosome<?, ?>> chromosomes = config.initialChromosomes();
    Any params = config.createParameters(chromosomes);
    
    assertThat(params.is(MassIndexParameters.class)).isTrue();
    MassIndexParameters massIndexParams = params.unpack(MassIndexParameters.class);
    
    assertThat(massIndexParams.getEmaPeriod()).isGreaterThan(0);
    assertThat(massIndexParams.getSumPeriod()).isGreaterThan(0);
  }

  @Test
  public void getStrategyType_returnsMassIndex() {
    assertThat(config.getStrategyType()).isEqualTo(Strategy.StrategyType.MASS_INDEX);
  }

  @Test
  public void validate_validParameters_doesNotThrow() {
    MassIndexParameters params = MassIndexParameters.newBuilder()
            .setEmaPeriod(25)
            .setSumPeriod(9)
            .build();

    config.validate(params); // Should not throw
  }

  @Test(expected = IllegalArgumentException.class)
  public void validate_invalidEmaPeriod_throwsException() {
    MassIndexParameters params = MassIndexParameters.newBuilder()
            .setEmaPeriod(0)
            .setSumPeriod(9)
            .build();

    config.validate(params);
  }

  @Test(expected = IllegalArgumentException.class)
  public void validate_invalidSumPeriod_throwsException() {
    MassIndexParameters params = MassIndexParameters.newBuilder()
            .setEmaPeriod(25)
            .setSumPeriod(0)
            .build();

    config.validate(params);
  }

  @Test
  public void unpack_validParameters_returnsCorrectValues() throws InvalidProtocolBufferException {
    MassIndexParameters expectedParams = MassIndexParameters.newBuilder()
            .setEmaPeriod(25)
            .setSumPeriod(9)
            .build();

    Any packedParams = Any.pack(expectedParams);
    MassIndexParameters unpackedParams = config.unpack(packedParams);

    assertThat(unpackedParams.getEmaPeriod()).isEqualTo(expectedParams.getEmaPeriod());
    assertThat(unpackedParams.getSumPeriod()).isEqualTo(expectedParams.getSumPeriod());
  }

  @Test(expected = InvalidProtocolBufferException.class)
  public void unpack_invalidType_throwsException() throws InvalidProtocolBufferException {
    Strategy strategy = Strategy.newBuilder()
            .setStrategyType(Strategy.StrategyType.RSI_EMA_CROSSOVER)
            .build();

    Any packedParams = Any.pack(strategy);
    config.unpack(packedParams);
  }
} 