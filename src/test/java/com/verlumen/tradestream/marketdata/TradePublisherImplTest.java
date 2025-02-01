package com.verlumen.tradestream.ingestion;

import static com.google.protobuf.util.Timestamps.fromMillis;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

import com.google.inject.assistedinject.FactoryModuleBuilder;
import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.testing.fieldbinder.Bind;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import org.apache.kafka.clients.producer.KafkaProducer;
import java.time.Duration; 
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
    
    @Mock @Bind private KafkaProducer<String, byte[]> mockProducer;
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
            .setCurrencyPair("BTC/USD")
            .setTimestamp(fromMillis(epochMillis))
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
