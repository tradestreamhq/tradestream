package com.verlumen.tradestream.strategies.trixsignalline;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.discovery.ParamConfig;
import com.verlumen.tradestream.strategies.TrixSignalLineParameters;
import io.jenetics.NumericChromosome;

/** Parameter configuration for TrixSignalLine genetic optimization. */
public final class TrixSignalLineParamConfig implements ParamConfig {

  private static final ImmutableList<ChromosomeSpec<?>> SPECS =
      ImmutableList.of(
          ChromosomeSpec.ofInteger(5, 50), // trixPeriod
          ChromosomeSpec.ofInteger(3, 20) // signalPeriod
          );

  @Override
  public ImmutableList<ChromosomeSpec<?>> getChromosomeSpecs() {
    return SPECS;
  }

  @Override
  public Any createParameters(ImmutableList<? extends NumericChromosome<?, ?>> chromosomes) {
    if (chromosomes.size() != SPECS.size()) {
      return getDefaultParameters();
    }

    try {
      int trixPeriod = chromosomes.get(0).gene().intValue();
      int signalPeriod = chromosomes.get(1).gene().intValue();

      // Ensure reasonable bounds
      trixPeriod = Math.max(5, Math.min(50, trixPeriod));
      signalPeriod = Math.max(3, Math.min(20, signalPeriod));

      TrixSignalLineParameters parameters =
          TrixSignalLineParameters.newBuilder()
              .setTrixPeriod(trixPeriod)
              .setSignalPeriod(signalPeriod)
              .build();

      return Any.pack(parameters);
    } catch (Exception e) {
      return getDefaultParameters();
    }
  }

  @Override
  public ImmutableList<? extends NumericChromosome<?, ?>> initialChromosomes() {
    return SPECS.stream()
        .map(ChromosomeSpec::createChromosome)
        .collect(ImmutableList.toImmutableList());
  }

  public Any getDefaultParameters() {
    TrixSignalLineParameters parameters =
        TrixSignalLineParameters.newBuilder().setTrixPeriod(15).setSignalPeriod(9).build();
    return Any.pack(parameters);
  }
}
