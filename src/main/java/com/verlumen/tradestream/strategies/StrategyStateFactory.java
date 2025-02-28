package com.verlumen.tradestream.strategies;

/**
 * Factory interface for creating instances of StrategyState.
 */
interface StrategyStateFactory {
    /**
     * Creates a new instance of StrategyState.
     *
     * @return a new StrategyState
     */
    StrategyState createStrategyState();
}
