package com.verlumen.tradestream.ingestion;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.testing.junit.testparameterinjector.TestParameterInjector;
import marketdata.Marketdata.Candle;
import org.apache.kafka.clients.producer.KafkaProducer;
import org.apache.kafka.clients.producer.ProducerRecord;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.mockito.Mock;

import java.time.Duration; 

@RunWith(TestParameterInjector.class)
public class CandlePublisherImplTest {
    private static final String TEST_TOPIC = "test-topic";
    
    @Mock @Bind
    private KafkaProducer<String, byte[]> mockProducer;
    @Inject
    private CandlePublisherImpl publisher;

    @Before
    public void setUp() {
        Guice.createInjector(BoundFieldModule.of(this)).injectMembers(this);
    }

    @Test
    public void publishCandle_sendsToKafka() {
        Candle candle = Candle.newBuilder()
            .setCurrencyPair("BTC/USD")
            .setTimestamp(System.currentTimeMillis())
            .build();

        publisher.publishCandle(candle);

        verify(mockProducer).send(any(ProducerRecord.class), any());
    }

    @Test
    public void close_closesProducer() {
        publisher.close();
        verify(mockProducer).close(any(Duration.class));
    }
}
