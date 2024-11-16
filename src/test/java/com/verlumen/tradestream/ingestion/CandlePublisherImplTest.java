package com.verlumen.tradestream.ingestion;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

import marketdata.Marketdata.Candle;
import org.apache.kafka.clients.producer.KafkaProducer;
import org.apache.kafka.clients.producer.ProducerRecord;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.mockito.Mock;
import org.mockito.MockitoAnnotations;
import com.google.testing.junit.testparameterinjector.TestParameterInjector;
import java.time.Duration; 

@RunWith(TestParameterInjector.class)
public class CandlePublisherImplTest {
    private static final String TEST_TOPIC = "test-topic";
    
    @Mock
    private KafkaProducer<String, byte[]> mockProducer;
    private CandlePublisherImpl publisher;

    @Before
    public void setUp() {
        MockitoAnnotations.openMocks(this);
        publisher = new CandlePublisherImpl(mockProducer, TEST_TOPIC);
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
