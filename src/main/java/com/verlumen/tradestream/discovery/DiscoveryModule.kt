package com.verlumen.tradestream.discovery

import com.google.inject.AbstractModule

class DiscoveryModule : AbstractModule() {
    override fun configure() {
        bind(GenotypeConverter::class.java).to(GenotypeConverterImpl::class.java)
        bind(ParamConfigManager::class.java).to(ParamConfigManagerImpl::class.java);
    }
}
