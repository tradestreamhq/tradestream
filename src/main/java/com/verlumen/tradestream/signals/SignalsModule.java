package com.verlumen.tradestream.signals;

import com.google.inject.AbstractModule;
import com.google.inject.assistedinject.FactoryModuleBuilder;

public final class SignalsModule extends AbstractModule {
    public static SignalsModule create() {
        return new SignalsModule();
    }

    @Override
    protected void configure() {
        install(new FactoryModuleBuilder()
            .implement(TradeSignalPublisher.class, TradeSignalPublisherImpl.class)
            .build(TradeSignalPublisher.Factory.class));
    }

    private SignalsModule() {}
}
