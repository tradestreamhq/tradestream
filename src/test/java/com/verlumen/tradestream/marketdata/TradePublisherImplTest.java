package com.verlumen.tradestream.marketdata;

import static com.google.protobuf.util.Timestamps.fromMillis;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verify;

import com.google.inject.assistedinject.FactoryModuleBuilder;
import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.testing.fieldbinder.Bind;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import org.apache.kafka.clients.producer.KafkaProducer;
import java.time.Duration; 
import java.util.function.Supplier;
import org.apache.kafka.clients.producer.ProducerRecord;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.mockito.Mock;
import org.mockito.junit.MockitoJUnit;
import org.mockito.junit.MockitoRule;

@RunWith(JUnit4.class)
public class TradePublisherImplTest {
    @Rule public MockitoRule mocks = MockitoJUnit.rule();

    private static final String TOPIC = "test-topic";

    @Mock private KafkaProducer<String, byte[]> mockProducer;
    @Bind private Supplier<KafkaProducer<String, byte[]>> kafkaProducerSupplier = () -> mockProducer;
    @Inject private TradePublisher.Factory factory;

    @Before
    public void setUp() {
        Guice
            .createInjector(
                BoundFieldModule.of(this), 
                new FactoryModuleBuilder()
                     .implement(TradePublisher.class, TradePublisherImpl.class)
                     .build(TradePublisher.Factory.class)
            )
            .injectMembers(this);
    }

    @Test
    public void publishTrade_sendsToKafka() {
        // Arrange
        long epochMillis = System.currentTimeMillis();
        Trade trade = Trade.newBuilder()
            .setExchange("Coinbase")
            .setCurrencyPair("BTC/USD")
            .setTradeId("trade-123")
            .setTimestamp(fromMillis(epochMillis))
            .setPrice(50000.0)
            .setVolume(0.1)
            .build();

        // Act
        factory.create(TOPIC).publishTrade(trade);

        // Assert
        verify(mockProducer).send(any(ProducerRecord.class), any());
    }

    @Test
    public void close_closesProducer() {
        // Act
        factory.create(TOPIC).close();

        // Assert
        verify(mockProducer).close(any(Duration.class));
    }
}
