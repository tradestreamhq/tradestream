package com.verlumen.tradestream.discovery

import com.google.inject.Inject
import com.verlumen.tradestream.backtesting.GAOptimizationRequest
import io.jenetics.*
import io.jenetics.engine.Engine
import java.util.logging.Logger

internal class GAEngineFactoryImpl
    @Inject
    constructor(
        private val paramConfigManager: ParamConfigManager,
        private val fitnessFunctionFactory: FitnessFunctionFactory,
    ) : GAEngineFactory {
        companion object {
            private val logger: Logger = Logger.getLogger(GAEngineFactoryImpl::class.java.name)
        }

        override fun createEngine(request: GAOptimizationRequest): Engine<*, Double> {
            // Create the initial genotype from the parameter specifications
            val gtf: Genotype<*> = createGenotype(request)

            // Build and return the GA engine with the specified settings
            // Assumption: fitnessFunctionFactory has a method `create` that matches this signature.
            // If it should be createFitnessFunction(request), adjust accordingly.
            val fitnessFunction = fitnessFunctionFactory.create(request.strategyType, request.candlesList)

            return Engine.builder(fitnessFunction, gtf)
                .populationSize(getPopulationSize(request))
                .selector(TournamentSelector<Gene<*,*>, Double>(GAConstants.TOURNAMENT_SIZE))
                .alterers(
                    Mutator<Gene<*,*>, Double>(GAConstants.MUTATION_PROBABILITY),
                    SinglePointCrossover<Gene<*,*>, Double>(GAConstants.CROSSOVER_PROBABILITY),
                ).build()
        }

        /**
         * Creates a genotype based on parameter specifications.
         *
         * @param request the GA optimization request
         * @return a genotype with chromosomes configured according to parameter specifications
         */
        private fun createGenotype(request: GAOptimizationRequest): Genotype<*> {
            try {
                val config: ParamConfig = paramConfigManager.getParamConfig(request.strategyType)

                // Get the chromosomes from the parameter configuration
                val numericChromosomes: List<NumericChromosome<*, *>> = config.initialChromosomes()

                if (numericChromosomes.isEmpty()) {
                    logger.warning("No chromosomes defined for strategy type: ${request.strategyType}")
                    return Genotype.of(DoubleChromosome.of(0.0, 1.0))
                }

                // For simplicity and to avoid generic type issues, we'll use the first chromosome as a
                // template and recreate all chromosomes to have the same type
                val firstChromosome: Chromosome<*> = numericChromosomes[0]

                return when (firstChromosome) {
                    is DoubleChromosome -> {
                        val doubleChromosomes =
                            numericChromosomes.map { chr ->
                                if (chr is DoubleChromosome) {
                                    chr
                                } else {
                                    // Convert to DoubleChromosome
                                    val value = chr.gene().doubleValue() // Assuming gene() returns NumericGene
                                    DoubleChromosome.of(value, value * 2) // Max value logic mirrored from Java
                                }
                            }
                        Genotype.of(doubleChromosomes)
                    }
                    is IntegerChromosome -> {
                        val integerChromosomes =
                            numericChromosomes.map { chr ->
                                if (chr is IntegerChromosome) {
                                    chr
                                } else {
                                    // Convert to IntegerChromosome
                                    val value = chr.gene().doubleValue().toInt() // Assuming gene() returns NumericGene
                                    IntegerChromosome.of(value, value * 2) // Max value logic mirrored from Java
                                }
                            }
                        Genotype.of(integerChromosomes)
                    }
                    else -> {
                        logger.warning(
                            "Unsupported chromosome type: ${firstChromosome.javaClass.name}. " +
                                "Using default DoubleChromosome.",
                        )
                        Genotype.of(DoubleChromosome.of(0.0, 1.0))
                    }
                }
            } catch (e: Exception) {
                logger.warning(
                    "Error creating genotype for strategy type ${request.strategyType}: ${e.message}",
                )
                // Fallback to a simple genotype with a single chromosome
                return Genotype.of(DoubleChromosome.of(0.0, 1.0))
            }
        }

        private fun getPopulationSize(request: GAOptimizationRequest): Int =
            if (request.populationSize > 0) {
                request.populationSize
            } else {
                GAConstants.DEFAULT_POPULATION_SIZE
            }
    }
