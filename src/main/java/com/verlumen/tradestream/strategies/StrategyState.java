package com.verlumen.tradestream.strategies;

import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import java.io.Serializable;
import org.ta4j.core.BarSeries;

/**
 * Interface for maintaining the state for the current strategy and
 * recording performance for all available strategies.
 */
public interface StrategyState extends Serializable {    
    /**
     * Reconstruct or return the current strategy.
     *
     * @param series the market data series
     * @return the current TA4J strategy
     * @throws InvalidProtocolBufferException if the strategy parameters are invalid
     */
    org.ta4j.core.Strategy getCurrentStrategy(BarSeries series) throws InvalidProtocolBufferException;
    
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
     * Get the type of the currently active strategy.
     *
     * @return the current strategy type
     */
    StrategyType getCurrentStrategyType();

    /**
     * Factory interface for creating instances of {@link StrategyState}.
     * <p>
     * Implementations of this interface should provide a method to
     * create a new instance of {@code StrategyState}, which is used to
     * initialize the state for a trading strategy.
     * </p>
     */
    interface Factory extends Serializable {
        /**
         * Creates and returns a new instance of {@link StrategyState}.
         *
         * @return a new instance of {@code StrategyState}
         */
        StrategyState create();
    }
}
