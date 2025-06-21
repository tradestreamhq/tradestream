package com.verlumen.tradestream.strategies.doubleemacrossover

import com.google.common.collect.ImmutableList
import com.google.protobuf.Any
import com.verlumen.tradestream.discovery.ChromosomeSpec
import com.verlumen.tradestream.discovery.ParamConfig
import com.verlumen.tradestream.strategies.DoubleEmaCrossoverParameters
import io.jenetics.IntegerChromosome
import io.jenetics.NumericChromosome

class DoubleEmaCrossoverParamConfig : ParamConfig {
    companion object {
        private val SPECS = ImmutableList.of(
            ChromosomeSpec.ofInteger(2, 30), // Short EMA Period
            ChromosomeSpec.ofInteger(10, 100) // Long EMA Period
        )
    }

    override fun getChromosomeSpecs(): ImmutableList<ChromosomeSpec<*>> = SPECS

    override fun createParameters(chromosomes: ImmutableList<out NumericChromosome<*, *>>): Any {
        require(chromosomes.size == SPECS.size) {
            "Expected ${SPECS.size} chromosomes but got ${chromosomes.size}"
        }

        val shortEmaPeriodChrom = chromosomes[0] as IntegerChromosome
        val longEmaPeriodChrom = chromosomes[1] as IntegerChromosome

        val parameters = DoubleEmaCrossoverParameters.newBuilder()
            .setShortEmaPeriod(shortEmaPeriodChrom.gene().allele())
            .setLongEmaPeriod(longEmaPeriodChrom.gene().allele())
            .build()

        return Any.pack(parameters)
    }

    override fun initialChromosomes(): ImmutableList<out NumericChromosome<*, *>> {
        return SPECS.stream()
            .map { it.createChromosome() }
            .collect(ImmutableList.toImmutableList())
    }
}
