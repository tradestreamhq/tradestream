package com.verlumen.tradestream.strategies.kstoscillator;

import static com.google.common.truth.Truth.assertThat;

import com.google.protobuf.Any;
import com.verlumen.tradestream.strategies.KstOscillatorParameters;
import io.jenetics.NumericChromosome;
import java.util.List;
import org.junit.Test;

public final class KstOscillatorParamConfigTest {
  private final KstOscillatorParamConfig config = new KstOscillatorParamConfig();

  @Test
  public void getChromosomeSpecs_returnsExpectedSpecs() {
    assertThat(config.getChromosomeSpecs()).hasSize(5);
  }

  @Test
  public void initialChromosomes_matchesSpecsSize() {
    assertThat(config.initialChromosomes()).hasSize(config.getChromosomeSpecs().size());
  }

  @Test
  public void createParameters_withDefaultChromosomes_returnsValidAny() throws Exception {
    List<? extends NumericChromosome<?, ?>> chromosomes = config.initialChromosomes();
    Any packed =
        config.createParameters(com.google.common.collect.ImmutableList.copyOf(chromosomes));
    assertThat(packed.is(KstOscillatorParameters.class)).isTrue();
    KstOscillatorParameters params = packed.unpack(KstOscillatorParameters.class);
    assertThat(params.getRma1Period()).isGreaterThan(0);
    assertThat(params.getRma2Period()).isGreaterThan(0);
    assertThat(params.getRma3Period()).isGreaterThan(0);
    assertThat(params.getRma4Period()).isGreaterThan(0);
    assertThat(params.getSignalPeriod()).isGreaterThan(0);
  }
}
