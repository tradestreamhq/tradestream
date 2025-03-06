package com.verlumen.tradestream.signals;

import com.google.auto.value.AutoValue;
import com.google.inject.AbstractModule;
import com.google.inject.assistedinject.FactoryModuleBuilder;

@AutoValue
public final class SignalsModule extends AbstractModule {
    public static SignalsModule create(String signalTopic) {
        return new AutoValue_SignalsModule(signalTopic);
    }

    abstract String signalTopic();

    @Override
    protected void configure() {
        install(new FactoryModuleBuilder()
            .implement(TradeSignalPublisher.class, TradeSignalPublisherImpl.class)
            .build(TradeSignalPublisher.Factory.class));
    }

    @Provides
    TradeSignalPublisher provideTradeSignalPublisher(TradeSignalPublisher.Factory factory) {
      return factory.create(signalTopic());
    }
}
