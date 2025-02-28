package com.verlumen.tradestream.strategies;

import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import org.ta4j.core.BarSeries;

/**
 * Interface for maintaining the state for the current strategy and
 * recording performance for all available strategies.
 */
interface StrategyState {
    
    /**
     * Reconstruct or return the current strategy.
     *
     * @param series the market data series
     * @return the current TA4J strategy
     * @throws InvalidProtocolBufferException if the strategy parameters are invalid
     */
    org.ta4j.core.Strategy getCurrentStrategy(BarSeries series)
            throws InvalidProtocolBufferException;
    
    /**
     * Update the record for a given strategy type.
     *
     * @param type the strategy type
     * @param parameters the parameters for the strategy
     * @param score the performance score
     */
    void updateRecord(StrategyType type, Any parameters, double score);
    
    /**
     * Select and initialize the best strategy from the recorded strategies.
     *
     * @param series the market data series
     * @return the updated strategy state
     */
    StrategyState selectBestStrategy(BarSeries series);
    
    /**
     * Convert the current state to a strategy message.
     *
     * @return the strategy message
     */
    Strategy toStrategyMessage();
    
    /**
     * Get all strategy types recorded.
     *
     * @return an iterable of strategy types
     */
    Iterable<StrategyType> getStrategyTypes();
    
    /**
     * Get the type of the currently active strategy.
     *
     * @return the current strategy type
     */
    StrategyType getCurrentStrategyType();
}
