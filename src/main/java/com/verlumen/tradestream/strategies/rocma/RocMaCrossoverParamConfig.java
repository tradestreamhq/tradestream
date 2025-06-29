package com.verlumen.tradestream.strategies.rocma;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.discovery.ParamConfig;
import com.verlumen.tradestream.strategies.RocMaCrossoverParameters;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;
import java.util.logging.Logger;

public final class RocMaCrossoverParamConfig implements ParamConfig {
  private static final Logger logger = Logger.getLogger(RocMaCrossoverParamConfig.class.getName());

  private static final ImmutableList<ChromosomeSpec<?>> SPECS =
      ImmutableList.of(
          ChromosomeSpec.ofInteger(5, 50), // rocPeriod
          ChromosomeSpec.ofInteger(5, 50)); // maPeriod

  @Override
  public ImmutableList<ChromosomeSpec<?>> getChromosomeSpecs() {
    return SPECS;
  }

  @Override
  public Any createParameters(ImmutableList<? extends NumericChromosome<?, ?>> chromosomes) {
    if (chromosomes.size() != 2) {
      logger.warning("Expected 2 chromosomes but got " + chromosomes.size());
      return Any.pack(
          RocMaCrossoverParameters.newBuilder().setRocPeriod(10).setMaPeriod(20).build());
    }

    try {
      int rocPeriod = ((IntegerChromosome) chromosomes.get(0)).intValue();
      int maPeriod = ((IntegerChromosome) chromosomes.get(1)).intValue();

      return Any.pack(
          RocMaCrossoverParameters.newBuilder()
              .setRocPeriod(rocPeriod)
              .setMaPeriod(maPeriod)
              .build());
    } catch (Exception e) {
      logger.warning("Error creating parameters: " + e.getMessage());
      return Any.pack(
          RocMaCrossoverParameters.newBuilder().setRocPeriod(10).setMaPeriod(20).build());
    }
  }

  @Override
  public ImmutableList<? extends NumericChromosome<?, ?>> initialChromosomes() {
    return SPECS.stream()
        .map(ChromosomeSpec::createChromosome)
        .collect(ImmutableList.toImmutableList());
  }
}
