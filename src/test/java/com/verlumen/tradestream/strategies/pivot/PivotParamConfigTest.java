package com.verlumen.tradestream.strategies.pivot;

import static com.google.common.truth.Truth.assertThat;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.discovery.ParamConfig;
import com.verlumen.tradestream.strategies.PivotParameters;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;
import java.util.logging.Logger;
import org.junit.Test;

public final class PivotParamConfigTest {
  private static final Logger logger = Logger.getLogger(PivotParamConfigTest.class.getName());
  private final ParamConfig config = new PivotParamConfig();

  @Test
  public void testChromosomeSpecs() {
    assertThat(config.getChromosomeSpecs()).hasSize(1);
  }

  @Test
  public void testInitialChromosomes() {
    assertThat(config.initialChromosomes()).hasSize(1);
  }

  @Test
  public void testCreateParameters_valid() throws InvalidProtocolBufferException {
    NumericChromosome<?, ?> periodChrom = IntegerChromosome.of(20, 21);
    Any packed = config.createParameters(ImmutableList.of(periodChrom));
    PivotParameters params = packed.unpack(PivotParameters.class);
    assertThat(params.getPeriod()).isEqualTo(20);
  }

  @Test
  public void testCreateParameters_invalid() throws InvalidProtocolBufferException {
    Any packed = config.createParameters(ImmutableList.of());
    PivotParameters params = packed.unpack(PivotParameters.class);
    assertThat(params.getPeriod()).isEqualTo(20); // default
  }
}
