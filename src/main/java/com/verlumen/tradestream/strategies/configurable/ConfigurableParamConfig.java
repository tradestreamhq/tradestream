package com.verlumen.tradestream.strategies.configurable;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.discovery.ParamConfig;
import com.verlumen.tradestream.strategies.ConfigurableStrategyParameters;
import io.jenetics.DoubleChromosome;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;
import java.util.List;

/**
 * A ParamConfig that reads parameter definitions from config. Generates ChromosomeSpecs for GA
 * optimization from config-defined ranges.
 */
public final class ConfigurableParamConfig implements ParamConfig {
  private static final long serialVersionUID = 1L;

  private final StrategyConfig config;
  private final ImmutableList<ChromosomeSpec<?>> specs;

  public ConfigurableParamConfig(StrategyConfig config) {
    this.config = config;
    this.specs = buildChromosomeSpecs();
  }

  private ImmutableList<ChromosomeSpec<?>> buildChromosomeSpecs() {
    if (config.getParameters() == null || config.getParameters().isEmpty()) {
      return ImmutableList.of();
    }

    ImmutableList.Builder<ChromosomeSpec<?>> builder = ImmutableList.builder();

    for (ParameterDefinition param : config.getParameters()) {
      ChromosomeSpec<?> spec =
          switch (param.getType()) {
            case INTEGER ->
                ChromosomeSpec.ofInteger(param.getMin().intValue(), param.getMax().intValue());
            case DOUBLE ->
                ChromosomeSpec.ofDouble(param.getMin().doubleValue(), param.getMax().doubleValue());
          };
      builder.add(spec);
    }

    return builder.build();
  }

  @Override
  public ImmutableList<ChromosomeSpec<?>> getChromosomeSpecs() {
    return specs;
  }

  @Override
  public Any createParameters(ImmutableList<? extends NumericChromosome<?, ?>> chromosomes) {
    List<ParameterDefinition> paramDefs = config.getParameters();

    if (paramDefs == null || paramDefs.isEmpty()) {
      return Any.pack(ConfigurableStrategyParameters.getDefaultInstance());
    }

    if (chromosomes.size() != paramDefs.size()) {
      throw new IllegalArgumentException(
          "Expected " + paramDefs.size() + " chromosomes but got " + chromosomes.size());
    }

    ConfigurableStrategyParameters.Builder builder = ConfigurableStrategyParameters.newBuilder();

    for (int i = 0; i < paramDefs.size(); i++) {
      ParameterDefinition def = paramDefs.get(i);
      NumericChromosome<?, ?> chromosome = chromosomes.get(i);

      switch (def.getType()) {
        case INTEGER -> {
          IntegerChromosome intChrom = (IntegerChromosome) chromosome;
          builder.putIntValues(def.getName(), intChrom.gene().allele());
        }
        case DOUBLE -> {
          DoubleChromosome doubleChrom = (DoubleChromosome) chromosome;
          builder.putDoubleValues(def.getName(), doubleChrom.gene().allele());
        }
      }
    }

    return Any.pack(builder.build());
  }

  @Override
  public ImmutableList<? extends NumericChromosome<?, ?>> initialChromosomes() {
    return specs.stream()
        .map(ChromosomeSpec::createChromosome)
        .collect(ImmutableList.toImmutableList());
  }

  public StrategyConfig getConfig() {
    return config;
  }
}
