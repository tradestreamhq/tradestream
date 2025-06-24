package com.verlumen.tradestream.strategies.trixsignalline;

import static com.google.common.truth.Truth.assertThat;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.strategies.TrixSignalLineParameters;
import io.jenetics.NumericChromosome;
import java.util.List;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;

@RunWith(JUnit4.class)
public final class TrixSignalLineParamConfigTest {

  private final TrixSignalLineParamConfig config = new TrixSignalLineParamConfig();

  @Test
  public void getChromosomeSpecs_returnsCorrectSize() {
    List<ChromosomeSpec<?>> specs = config.getChromosomeSpecs();
    assertThat(specs).hasSize(2);
  }

  @Test
  public void initialChromosomes_returnsCorrectSize() {
    List<? extends NumericChromosome<?, ?>> chromosomes = config.initialChromosomes();
    assertThat(chromosomes).hasSize(2);
  }

  @Test
  public void createParameters_withValidChromosomes_returnsAny()
      throws InvalidProtocolBufferException {
    ImmutableList<? extends NumericChromosome<?, ?>> chromosomes =
        ImmutableList.copyOf(config.initialChromosomes());
    Any result = config.createParameters(chromosomes);
    assertThat(result).isNotNull();
    TrixSignalLineParameters params = result.unpack(TrixSignalLineParameters.class);
    assertThat(params.getTrixPeriod()).isAtLeast(5);
    assertThat(params.getSignalPeriod()).isAtLeast(3);
  }

  @Test
  public void createParameters_withInvalidChromosomes_returnsDefault()
      throws InvalidProtocolBufferException {
    // Create invalid chromosomes (empty list)
    ImmutableList<NumericChromosome<?, ?>> invalidChromosomes = ImmutableList.of();
    Any result = config.createParameters(invalidChromosomes);
    assertThat(result).isNotNull();
    TrixSignalLineParameters params = result.unpack(TrixSignalLineParameters.class);
    assertThat(params.getTrixPeriod()).isEqualTo(15);
    assertThat(params.getSignalPeriod()).isEqualTo(9);
  }

  @Test
  public void getDefaultParameters_returnsValidParameters() throws InvalidProtocolBufferException {
    Any result = config.getDefaultParameters();

    assertThat(result).isNotNull();
    TrixSignalLineParameters params = result.unpack(TrixSignalLineParameters.class);
    assertThat(params.getTrixPeriod()).isEqualTo(15);
    assertThat(params.getSignalPeriod()).isEqualTo(9);
  }
}
