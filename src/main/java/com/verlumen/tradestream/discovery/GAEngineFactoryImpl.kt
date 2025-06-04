package com.verlumen.tradestream.discovery

import com.google.inject.Inject
import com.verlumen.tradestream.backtesting.GAOptimizationRequest
import io.jenetics.Chromosome
import io.jenetics.DoubleChromosome
import io.jenetics.Genotype
import io.jenetics.IntegerChromosome
import io.jenetics.Mutator
import io.jenetics.NumericChromosome
import io.jenetics.SinglePointCrossover
import io.jenetics.TournamentSelector
import io.jenetics.engine.Engine
import java.util.logging.Logger

class GAEngineFactoryImpl @Inject constructor(
    private val paramConfigManager: ParamConfigManager,
    private val fitnessFunctionFactory: FitnessFunctionFactory
) : GAEngineFactory {

    companion object {
        private val logger = Logger.getLogger(GAEngineFactoryImpl::class.java.name)
    }

    override fun createEngine(request: GAOptimizationRequest): Engine<*, Double> {
        // Create the initial genotype from the parameter specifications
        val gtf = createGenotype(request)

        // Build and return the GA engine with the specified settings
        return Engine.builder(
            fitnessFunctionFactory.create(request.strategyType, request.candlesList),
            gtf
        )
            .populationSize(getPopulationSize(request))
            .selector(TournamentSelector<Any>(GAConstants.TOURNAMENT_SIZE))
            .alterers(
                Mutator<Any>(GAConstants.MUTATION_PROBABILITY),
                SinglePointCrossover<Any>(GAConstants.CROSSOVER_PROBABILITY)
            )
            .build()
    }

    /**
     * Creates a genotype based on parameter specifications.
     *
     * @param request the GA optimization request
     * @return a genotype with chromosomes configured according to parameter specifications
     */
    private fun createGenotype(request: GAOptimizationRequest): Genotype<*> {
        return try {
            val config = paramConfigManager.getParamConfig(request.strategyType)

            // Get the chromosomes from the parameter configuration
            val numericChromosomes = config.initialChromosomes()

            if (numericChromosomes.isEmpty()) {
                logger.warning("No chromosomes defined for strategy type: ${request.strategyType}")
                return Genotype.of(DoubleChromosome.of(0.0, 1.0))
            }

            // For simplicity and to avoid generic type issues, we'll use the first chromosome as a
            // template and recreate all chromosomes to have the same type
            val firstChromosome = numericChromosomes[0]

            when (firstChromosome) {
                is DoubleChromosome -> {
                    // Handle case where we need DoubleChromosome type
                    val doubleChromosomes = mutableListOf<DoubleChromosome>()
                    for (chr in numericChromosomes) {
                        if (chr is DoubleChromosome) {
                            doubleChromosomes.add(chr)
                        } else {
                            // Convert to DoubleChromosome
                            val value = chr.gene().doubleValue()
                            doubleChromosomes.add(DoubleChromosome.of(value, value * 2))
                        }
                    }
                    Genotype.of(doubleChromosomes)
                }
                is IntegerChromosome -> {
                    // Handle case where we need IntegerChromosome type
                    val integerChromosomes = mutableListOf<IntegerChromosome>()
                    for (chr in numericChromosomes) {
                        if (chr is IntegerChromosome) {
                            integerChromosomes.add(chr)
                        } else {
                            // Convert to IntegerChromosome
                            val value = chr.gene().doubleValue().toInt()
                            integerChromosomes.add(IntegerChromosome.of(value, value * 2))
                        }
                    }
                    Genotype.of(integerChromosomes)
                }
                else -> {
                    // Default to DoubleChromosome if the type is unknown
                    logger.warning(
                        "Unsupported chromosome type: ${firstChromosome::class.java.name}. " +
                            "Using default DoubleChromosome."
                    )
                    Genotype.of(DoubleChromosome.of(0.0, 1.0))
                }
            }
        } catch (e: Exception) {
            logger.warning(
                "Error creating genotype for strategy type ${request.strategyType}: ${e.message}"
            )
            // Fallback to a simple genotype with a single chromosome
            Genotype.of(DoubleChromosome.of(0.0, 1.0))
        }
    }

    private fun getPopulationSize(request: GAOptimizationRequest): Int {
        return if (request.populationSize > 0) {
            request.populationSize
        } else {
            GAConstants.DEFAULT_POPULATION_SIZE
        }
    }
}
