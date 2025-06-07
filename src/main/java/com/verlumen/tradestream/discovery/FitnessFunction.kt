package com.verlumen.tradestream.discovery

import io.jenetics.Genotype
import java.util.function.Function

/**
 * Type alias for fitness functions used in genetic algorithms.
 * Takes a Genotype and returns a Double fitness score.
 */
typealias FitnessFunction = Function<Genotype<*>, Double>
