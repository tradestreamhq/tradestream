package com.verlumen.tradestream.backtesting;

import io.jenetics.DoubleGene;
import io.jenetics.engine.Engine;

/**
 * Defines the contract for creating genetic algorithm engines.
 */
interface GAEngineFactory {
    /**
     * Creates a genetic algorithm engine configured for the given request.
     *
     * @param request the GA optimization request
     * @return a configured GA engine
     */
    Engine<DoubleGene, Double> createEngine(GAOptimizationRequest request);
}
