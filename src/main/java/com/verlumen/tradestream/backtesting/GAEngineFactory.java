package com.verlumen.tradestream.backtesting;

import io.jenetics.Gene;
import io.jenetics.engine.Engine;
import java.io.Serializable;

/**
 * Defines the contract for creating genetic algorithm engines.
 */
interface GAEngineFactory extends Serializable {
    /**
     * Creates a genetic algorithm engine configured for the given request.
     *
     * @param request the GA optimization request
     * @return a configured GA engine
     */
    Engine<?, Double> createEngine(GAOptimizationRequest request);
}
