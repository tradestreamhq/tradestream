package com.verlumen.tradestream.strategies.regressionchannel;

import static com.google.common.truth.Truth.assertThat;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.discovery.ParamConfig;
import com.verlumen.tradestream.strategies.RegressionChannelParameters;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;
import java.util.logging.Logger;
import org.junit.Test;

public final class RegressionChannelParamConfigTest {
  private static final Logger logger =
      Logger.getLogger(RegressionChannelParamConfigTest.class.getName());
  private final ParamConfig config = new RegressionChannelParamConfig();

  @Test
  public void testChromosomeSpecs() {
    assertThat(config.getChromosomeSpecs().size()).isEqualTo(1);
  }

  @Test
  public void testInitialChromosomes() {
    assertThat(config.initialChromosomes().size()).isEqualTo(1);
  }

  @Test
  public void testCreateParameters_valid() throws InvalidProtocolBufferException {
    NumericChromosome<?, ?> periodChrom = IntegerChromosome.of(30, 31);
    Any packed = config.createParameters(ImmutableList.of(periodChrom));
    RegressionChannelParameters params = packed.unpack(RegressionChannelParameters.class);
    assertThat(params.getPeriod()).isEqualTo(30);
  }

  @Test
  public void testCreateParameters_invalidSize() throws InvalidProtocolBufferException {
    Any packed = config.createParameters(ImmutableList.of());
    RegressionChannelParameters params = packed.unpack(RegressionChannelParameters.class);
    assertThat(params.getPeriod()).isEqualTo(20); // default
  }

  @Test
  public void testCreateParameters_invalidType() throws InvalidProtocolBufferException {
    // Use a chromosome with a value outside the allowed range
    NumericChromosome<?, ?> periodChrom = IntegerChromosome.of(200, 201);
    Any packed = config.createParameters(ImmutableList.of(periodChrom));
    RegressionChannelParameters params = packed.unpack(RegressionChannelParameters.class);
    // Should still set the value, but the config should handle out-of-range gracefully
    assertThat(params.getPeriod()).isEqualTo(200);
  }
}
