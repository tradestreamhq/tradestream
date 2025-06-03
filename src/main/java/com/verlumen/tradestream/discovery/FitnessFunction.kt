package com.verlumen.tradestream.discovery

import io.jenetics.Genotype
import java.util.Function

typealias FitnessFunction = Function<Genotype<*>, Double>
