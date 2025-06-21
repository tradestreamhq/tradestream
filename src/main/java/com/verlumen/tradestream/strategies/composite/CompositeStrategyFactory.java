package com.verlumen.tradestream.strategies.composite;

import static com.google.common.base.Preconditions.checkArgument;

import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.CompositeStrategyParameters;
import com.verlumen.tradestream.strategies.CompositeStrategyParameters.LogicalOperator;
import com.verlumen.tradestream.strategies.StrategyFactory;
import com.verlumen.tradestream.strategies.StrategyType;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseStrategy;
import org.ta4j.core.Rule;
import org.ta4j.core.Strategy;

public final class CompositeStrategyFactory implements StrategyFactory<CompositeStrategyParameters> {
  
  // Maximum nesting depth to prevent infinite recursion
  private static final int MAX_NESTING_DEPTH = 5;
  
  @Override
  public Strategy createStrategy(BarSeries series, CompositeStrategyParameters params)
      throws InvalidProtocolBufferException {
    validateParameters(params);
    
    return createStrategyWithDepth(series, params, 0);
  }
  
  private Strategy createStrategyWithDepth(BarSeries series, CompositeStrategyParameters params, int depth)
      throws InvalidProtocolBufferException {
    checkArgument(depth <= MAX_NESTING_DEPTH, 
        "Maximum nesting depth exceeded: %s. This may indicate infinite recursion.", MAX_NESTING_DEPTH);
    
    // Create the constituent strategies
    Strategy leftStrategy = createConstituentStrategy(series, params.getLeftStrategy(), depth + 1);
    Strategy rightStrategy = createConstituentStrategy(series, params.getRightStrategy(), depth + 1);
    
    // Compose the rules based on operators
    Rule entryRule = composeRules(
        leftStrategy.getEntryRule(),
        rightStrategy.getEntryRule(),
        params.getEntryOperator()
    );
    
    Rule exitRule = composeRules(
        leftStrategy.getExitRule(),
        rightStrategy.getExitRule(),
        params.getExitOperator()
    );
    
    // Calculate unstable bars as the maximum of constituent strategies
    int unstableBars = Math.max(leftStrategy.getUnstableBars(), rightStrategy.getUnstableBars());
    
    return new BaseStrategy(
        generateStrategyName(params),
        entryRule,
        exitRule,
        unstableBars
    );
  }
  
  private Strategy createConstituentStrategy(BarSeries series, 
      com.verlumen.tradestream.strategies.Strategy strategyDef, int depth) 
      throws InvalidProtocolBufferException {
    if (strategyDef.getType() == StrategyType.COMPOSITE) {
      // Handle nested composite strategies
      CompositeStrategyParameters nestedParams = strategyDef.getParameters()
          .unpack(CompositeStrategyParameters.class);
      return createStrategyWithDepth(series, nestedParams, depth);
    } else {
      // Create regular strategy using the extension methods
      return strategyDef.getType().createStrategy(series, strategyDef.getParameters());
    }
  }
  
  private Rule composeRules(Rule leftRule, Rule rightRule, LogicalOperator operator) {
    return switch (operator) {
      case AND -> leftRule.and(rightRule);
      case OR -> leftRule.or(rightRule);
    };
  }
  
  private String generateStrategyName(CompositeStrategyParameters params) {
    String leftName = extractStrategyName(params.getLeftStrategy());
    String rightName = extractStrategyName(params.getRightStrategy());
    String entryOp = params.getEntryOperator().name();
    String exitOp = params.getExitOperator().name();
    
    if (entryOp.equals(exitOp)) {
      return String.format("COMPOSITE (%s %s %s)", leftName, entryOp, rightName);
    } else {
      return String.format("COMPOSITE (%s) Entry:%s Exit:%s (%s)", 
          leftName, entryOp, exitOp, rightName);
    }
  }
  
  private String extractStrategyName(com.verlumen.tradestream.strategies.Strategy strategy) {
    if (strategy.getType() == StrategyType.COMPOSITE) {
      return "COMPOSITE";
    } else {
      return strategy.getType().name();
    }
  }
  
  private void validateParameters(CompositeStrategyParameters params) {
    checkArgument(params.hasLeftStrategy(), "Left strategy is required");
    checkArgument(params.hasRightStrategy(), "Right strategy is required");
    checkArgument(params.getLeftStrategy().hasType(), "Left strategy type is required");
    checkArgument(params.getRightStrategy().hasType(), "Right strategy type is required");
    checkArgument(params.hasEntryOperator(), "Entry operator is required");
    checkArgument(params.hasExitOperator(), "Exit operator is required");
    
    // Prevent self-referential composite strategies at the top level
    checkArgument(params.getLeftStrategy().getType() != StrategyType.UNSPECIFIED,
        "Left strategy type cannot be UNSPECIFIED");
    checkArgument(params.getRightStrategy().getType() != StrategyType.UNSPECIFIED,
        "Right strategy type cannot be UNSPECIFIED");
  }
  
  @Override
  public CompositeStrategyParameters getDefaultParameters() {
    // Create default constituent strategies
    var defaultSmaRsi = com.verlumen.tradestream.strategies.Strategy.newBuilder()
        .setType(StrategyType.SMA_RSI)
        .setParameters(StrategyType.SMA_RSI.getDefaultParameters())
        .build();
        
    var defaultEmaMacd = com.verlumen.tradestream.strategies.Strategy.newBuilder()
        .setType(StrategyType.EMA_MACD)
        .setParameters(StrategyType.EMA_MACD.getDefaultParameters())
        .build();
    
    return CompositeStrategyParameters.newBuilder()
        .setLeftStrategy(defaultSmaRsi)
        .setRightStrategy(defaultEmaMacd)
        .setEntryOperator(LogicalOperator.AND)  // Conservative: both must agree to enter
        .setExitOperator(LogicalOperator.OR)    // Aggressive: either can trigger exit
        .build();
  }
}
