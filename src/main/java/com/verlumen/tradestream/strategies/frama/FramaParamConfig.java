package com.verlumen.tradestream.strategies.frama;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.discovery.ParamConfig;
import com.verlumen.tradestream.strategies.FramaParameters;
import io.jenetics.DoubleChromosome;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;
import java.util.logging.Logger;

public final class FramaParamConfig implements ParamConfig {
  private static final Logger logger = Logger.getLogger(FramaParamConfig.class.getName());

  private static final ImmutableList<ChromosomeSpec<?>> SPECS =
      ImmutableList.of(
          ChromosomeSpec.ofDouble(0.1, 2.0), // sc
          ChromosomeSpec.ofInteger(5, 50), // fc
          ChromosomeSpec.ofDouble(0.1, 1.0)); // alpha

  @Override
  public ImmutableList<ChromosomeSpec<?>> getChromosomeSpecs() {
    return SPECS;
  }

  @Override
  public Any createParameters(ImmutableList<? extends NumericChromosome<?, ?>> chromosomes) {
    if (chromosomes.size() != 3) {
      logger.warning("Expected 3 chromosomes but got " + chromosomes.size());
      return Any.pack(FramaParameters.newBuilder().setSc(0.5).setFc(20).setAlpha(0.5).build());
    }

    try {
      double sc = ((DoubleChromosome) chromosomes.get(0)).doubleValue();
      int fc = ((IntegerChromosome) chromosomes.get(1)).intValue();
      double alpha = ((DoubleChromosome) chromosomes.get(2)).doubleValue();

      return Any.pack(FramaParameters.newBuilder().setSc(sc).setFc(fc).setAlpha(alpha).build());
    } catch (Exception e) {
      logger.warning("Error creating parameters: " + e.getMessage());
      return Any.pack(FramaParameters.newBuilder().setSc(0.5).setFc(20).setAlpha(0.5).build());
    }
  }

  @Override
  public ImmutableList<? extends NumericChromosome<?, ?>> initialChromosomes() {
    return SPECS.stream()
        .map(ChromosomeSpec::createChromosome)
        .collect(ImmutableList.toImmutableList());
  }
}
