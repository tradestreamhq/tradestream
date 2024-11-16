package com.verlumen.tradestream.ingestion;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.testing.fieldbinder.Bind;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import marketdata.Marketdata.Candle;
import org.apache.kafka.clients.producer.KafkaProducer;
import org.apache.kafka.clients.producer.ProducerRecord;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.mockito.Mock;
import org.mockito.junit.MockitoJUnit;
import org.mockito.junit.MockitoRule;
import java.time.Duration; 

@RunWith(JUnit4.class)
public class CandlePublisherImplTest {
    @Rule public MockitoRule mocks = MockitoJUnit.rule();

    private static final String TEST_TOPIC = "test-topic";
    
    @Mock private KafkaProducer<String, byte[]> mockProducer;
    @Inject private CandlePublisherImpl publisher;

    @Before
    public void setUp() {
        publisher = new CandlePublisherImpl(TEST_TOPIC, mockProducer);
    }

    @Test
    public void publishCandle_sendsToKafka() {
        // Arrange
        Candle candle = Candle.newBuilder()
            .setCurrencyPair("BTC/USD")
            .setTimestamp(System.currentTimeMillis())
            .build();

        // Act
        publisher.publishCandle(candle);

        // Assert
        verify(mockProducer).send(any(ProducerRecord.class), any());
    }

    @Test
    public void close_closesProducer() {
        // Act
        publisher.close();

        // Assert
        verify(mockProducer).close(any(Duration.class));
    }
}
