package com.verlumen.tradestream.signals;

import static com.google.common.truth.Truth.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.assistedinject.FactoryModuleBuilder;
import com.google.inject.testing.fieldbinder.Bind;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import com.verlumen.tradestream.strategies.Strategy;
import com.verlumen.tradestream.strategies.StrategyType;
import java.time.Duration;
import java.util.function.Supplier;
import org.apache.kafka.clients.producer.KafkaProducer;
import org.apache.kafka.clients.producer.ProducerRecord;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.MockitoJUnit;
import org.mockito.junit.MockitoRule;

@RunWith(JUnit4.class)
public class TradeSignalPublisherImplTest {
    @Rule public MockitoRule mocks = MockitoJUnit.rule();

    private static final String TOPIC = "test-topic";
    
    @Mock private KafkaProducer<String, byte[]> mockProducer;
    @Bind private Supplier<KafkaProducer<String, byte[]>> kafkaProducerSupplier = () -> mockProducer;
    @Inject private TradeSignalPublisher.Factory factory;

    @Before
    public void setUp() {
        Guice
            .createInjector(
                BoundFieldModule.of(this), 
                new FactoryModuleBuilder()
                     .implement(TradeSignalPublisher.class, TradeSignalPublisherImpl.class)
                     .build(TradeSignalPublisher.Factory.class)
            )
            .injectMembers(this);
    }

    @Test
    public void publish_sendsToKafka() {
        // Arrange
        TradeSignal signal = createTestSignal();

        // Act
        factory.create(TOPIC).publish(signal);

        // Assert
        verify(mockProducer).send(any(ProducerRecord.class), any());
    }

    @Test
    public void publish_usesStrategyTypeAsKey() {
        // Arrange
        ArgumentCaptor<ProducerRecord<String, byte[]>> recordCaptor = 
            ArgumentCaptor.forClass(ProducerRecord.class);
        TradeSignal signal = createTestSignal();

        // Act
        factory.create(TOPIC).publish(signal);

        // Assert
        verify(mockProducer).send(recordCaptor.capture(), any());
        ProducerRecord<String, byte[]> record = recordCaptor.getValue();
        assertThat(record.key()).isEqualTo(signal.getStrategy().getType().name());
    }

    @Test
    public void close_closesProducer() {
        // Act
        factory.create(TOPIC).close();

        // Assert
        verify(mockProducer).flush();
        verify(mockProducer).close(any(Duration.class));
    }

    private TradeSignal createTestSignal() {
        return TradeSignal.newBuilder()
            .setType(TradeSignal.TradeSignalType.BUY)
            .setTimestamp(System.currentTimeMillis())
            .setPrice(50000.0)
            .setStrategy(Strategy.newBuilder()
                .setType(StrategyType.SMA_RSI)
                .build())
            .build();
    }
}
