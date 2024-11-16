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
    
    @Mock @Bind private KafkaProducer<String, byte[]> mockProducer;
    @Inject private CandlePublisher.Factory factory;

    @Before
    public void setUp() {
        Guice.createInjector(BoundFieldModule.of(this), new TestModule()).injectMembers(this);
    }

    @Test
    public void publishCandle_sendsToKafka() {
        // Arrange
        Candle candle = Candle.newBuilder()
            .setCurrencyPair("BTC/USD")
            .setTimestamp(System.currentTimeMillis())
            .build();

        // Act
        factory.create(TEST_TOPIC).publishCandle(candle);

        // Assert
        verify(mockProducer).send(any(ProducerRecord.class), any());
    }

    @Test
    public void close_closesProducer() {
        // Act
        factory.create(TEST_TOPIC).close();

        // Assert
        verify(mockProducer).close(any(Duration.class));
    }

    private static class TestModule extends AbstractModule {
        @Override
        protected void configure() {
            bind(CandlePublisher.Factory.class).to(CandlePublisherImplFactory.class);
        }
    }
}
