package com.verlumen.tradestream.strategies;

import com.verlumen.tradestream.marketdata.Candle;

interface StrategyEngine {
    /**
     * Handles new candle data from the market
     */
    void handleCandle(Candle candle);
    
    /**
     * Requests optimization of strategy parameters
     */
    void optimizeStrategy();
    
    /**
     * Gets the current active strategy
     */
    Strategy getCurrentStrategy();
}
