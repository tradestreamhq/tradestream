package com.verlumen.tradestream.ingestion;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

import marketdata.Marketdata.Candle;
import org.apache.kafka.clients.producer.KafkaProducer;
import org.apache.kafka.clients.producer.ProducerRecord;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.mockito.Mock;
import org.mockito.junit.MockitoJUnit;
import org.mockito.junit.MockitoRule;
import com.google.testing.junit.testparameterinjector.TestParameterInjector;
import java.time.Duration; 


import com.google.testing.junit.testparameterinjector.TestParameterInjector;

@RunWith(TestParameterInjector.class)
public class CandlePublisherImplTest {
    @Rule public MockitoRule rule = MockitoJUnit.rule();

    private static final String TEST_TOPIC = "test-topic";
    
    @Mock
    private KafkaProducer<String, byte[]> mockProducer;
    private CandlePublisherImpl publisher;

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
