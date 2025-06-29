package com.verlumen.tradestream.discovery

import io.jenetics.engine.Engine
import java.io.Serializable

/** Defines the contract for creating genetic algorithm engines. */
interface GAEngineFactory : Serializable {
    /**
     * Creates a genetic algorithm engine configured for the given request.
     *
     * @param params The parameters for configuring the GA engine.
     * @return a configured GA engine
     */
    fun createEngine(params: GAEngineParams): Engine<*, Double>
}
