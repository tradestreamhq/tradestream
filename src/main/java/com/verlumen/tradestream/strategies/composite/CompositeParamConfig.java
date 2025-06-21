package com.verlumen.tradestream.strategies.composite;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.discovery.ParamConfig;
import com.verlumen.tradestream.strategies.CompositeStrategyParameters;
import com.verlumen.tradestream.strategies.CompositeStrategyParameters.LogicalOperator;
import com.verlumen.tradestream.strategies.StrategyType;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;
import java.util.EnumSet;

/**
 * Parameter configuration for CompositeStrategy genetic optimization.
 * 
 * This implementation uses a simplified approach where:
 * - Only a predefined set of "base" strategies can be combined
 * - Sub-strategies use their default parameters (not optimized)
 * - Only the strategy selection and operators are optimized
 * 
 * Future enhancements could include optimizing the parameters of constituent strategies.
 */
public final class CompositeParamConfig implements ParamConfig {
  
  // Base strategies that can be combined (avoiding COMPOSITE to prevent infinite recursion)
  private static final ImmutableList<StrategyType> BASE_STRATEGIES =
      ImmutableList.copyOf(
          EnumSet.complementOf(
              EnumSet.of(
                  StrategyType.UNRECOGNIZED,
                  StrategyType.UNSPECIFIED,
                  StrategyType.COMPOSITE
              )
          )
      );
  
  private static final ImmutableList<ChromosomeSpec<?>> SPECS = ImmutableList.of(
      // Left strategy selection (index into BASE_STRATEGIES)
      ChromosomeSpec.ofInteger(0, BASE_STRATEGIES.size() - 1),
      // Right strategy selection (index into BASE_STRATEGIES) 
      ChromosomeSpec.ofInteger(0, BASE_STRATEGIES.size() - 1),
      // Entry operator (0 = AND, 1 = OR)
      ChromosomeSpec.ofInteger(0, 1),
      // Exit operator (0 = AND, 1 = OR)
      ChromosomeSpec.ofInteger(0, 1)
  );
  
  @Override
  public ImmutableList<ChromosomeSpec<?>> getChromosomeSpecs() {
    return SPECS;
  }
  
  @Override
  public Any createParameters(ImmutableList<? extends NumericChromosome<?, ?>> chromosomes) {
    if (chromosomes.size() != SPECS.size()) {
      throw new IllegalArgumentException(
          "Expected " + SPECS.size() + " chromosomes but got " + chromosomes.size());
    }
    
    // Extract values from chromosomes
    IntegerChromosome leftStrategyChrom = (IntegerChromosome) chromosomes.get(0);
    IntegerChromosome rightStrategyChrom = (IntegerChromosome) chromosomes.get(1);
    IntegerChromosome entryOperatorChrom = (IntegerChromosome) chromosomes.get(2);
    IntegerChromosome exitOperatorChrom = (IntegerChromosome) chromosomes.get(3);
    
    int leftStrategyIndex = leftStrategyChrom.gene().allele();
    int rightStrategyIndex = rightStrategyChrom.gene().allele();
    int entryOperatorValue = entryOperatorChrom.gene().allele();
    int exitOperatorValue = exitOperatorChrom.gene().allele();
    
    // Get strategy types
    StrategyType leftStrategyType = BASE_STRATEGIES.get(leftStrategyIndex);
    StrategyType rightStrategyType = BASE_STRATEGIES.get(rightStrategyIndex);
    
    // Convert operator values to enum
    LogicalOperator entryOperator = (entryOperatorValue == 0) ? LogicalOperator.AND : LogicalOperator.OR;
    LogicalOperator exitOperator = (exitOperatorValue == 0) ? LogicalOperator.AND : LogicalOperator.OR;
    
    // Create strategy definitions with default parameters
    var leftStrategy = com.verlumen.tradestream.strategies.Strategy.newBuilder()
        .setType(leftStrategyType)
        .setParameters(leftStrategyType.getDefaultParameters())
        .build();
        
    var rightStrategy = com.verlumen.tradestream.strategies.Strategy.newBuilder()
        .setType(rightStrategyType)
        .setParameters(rightStrategyType.getDefaultParameters())
        .build();
    
    // Build composite parameters
    CompositeStrategyParameters parameters = CompositeStrategyParameters.newBuilder()
        .setLeftStrategy(leftStrategy)
        .setRightStrategy(rightStrategy)
        .setEntryOperator(entryOperator)
        .setExitOperator(exitOperator)
        .build();
    
    return Any.pack(parameters);
  }
  
  @Override
  public ImmutableList<? extends NumericChromosome<?, ?>> initialChromosomes() {
    return SPECS.stream()
        .map(ChromosomeSpec::createChromosome)
        .collect(ImmutableList.toImmutableList());
  }
  
  /**
   * Gets the list of base strategies that can be combined.
   * Useful for testing and debugging.
   */
  public static ImmutableList<StrategyType> getBaseStrategies() {
    return BASE_STRATEGIES;
  }
}
