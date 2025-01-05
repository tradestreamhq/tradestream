package com.verlumen.tradestream.signals;

import com.google.inject.AbstractModule;

final class SignalsModule extends AbstractModule {
    @Override
    protected void configure() {
        install(new FactoryModuleBuilder()
            .implement(TradeSignalPublisher.class, TradeSignalPublisherImpl.class)
            .build(TradeSignalPublisher.Factory.class));
    }
}