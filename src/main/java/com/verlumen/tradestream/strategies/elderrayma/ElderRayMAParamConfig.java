package com.verlumen.tradestream.strategies.elderrayma;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.discovery.ParamConfig;
import com.verlumen.tradestream.strategies.ElderRayMAParameters;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;
import java.util.logging.Logger;

public final class ElderRayMAParamConfig implements ParamConfig {
  private static final Logger logger = Logger.getLogger(ElderRayMAParamConfig.class.getName());

  private static final ImmutableList<ChromosomeSpec<?>> SPECS =
      ImmutableList.of(ChromosomeSpec.ofInteger(5, 50));

  @Override
  public ImmutableList<ChromosomeSpec<?>> getChromosomeSpecs() {
    return SPECS;
  }

  @Override
  public Any createParameters(ImmutableList<? extends NumericChromosome<?, ?>> chromosomes) {
    if (chromosomes.size() != 1) {
      logger.warning("Expected 1 chromosome but got " + chromosomes.size());
      return Any.pack(getDefaultParameters());
    }

    try {
      int emaPeriod = ((IntegerChromosome) chromosomes.get(0)).intValue();

      ElderRayMAParameters parameters =
          ElderRayMAParameters.newBuilder().setEmaPeriod(emaPeriod).build();

      return Any.pack(parameters);
    } catch (Exception e) {
      logger.warning("Error creating parameters: " + e.getMessage());
      return Any.pack(getDefaultParameters());
    }
  }

  @Override
  public ImmutableList<? extends NumericChromosome<?, ?>> initialChromosomes() {
    return SPECS.stream()
        .map(ChromosomeSpec::createChromosome)
        .collect(ImmutableList.toImmutableList());
  }

  private ElderRayMAParameters getDefaultParameters() {
    return ElderRayMAParameters.newBuilder().setEmaPeriod(20).build();
  }
}
