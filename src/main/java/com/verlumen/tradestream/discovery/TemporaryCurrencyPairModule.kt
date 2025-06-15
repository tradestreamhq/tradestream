package com.verlumen.tradestream.discovery

import com.google.common.collect.ImmutableList
import com.google.inject.AbstractModule
import com.google.inject.TypeLiteral
import com.verlumen.tradestream.instruments.CurrencyPair
import java.util.function.Supplier

// TODO: delete this module as soon as we remove all remaining dependencies
class TemporaryCurrencyPairModule : AbstractModule() {
    override fun configure() {
        bind(object : TypeLiteral<Supplier<java.util.List<CurrencyPair>>>() {}).toInstance(Supplier {
            ImmutableList.of<CurrencyPair>() as java.util.List<CurrencyPair>
        })
    }
}
