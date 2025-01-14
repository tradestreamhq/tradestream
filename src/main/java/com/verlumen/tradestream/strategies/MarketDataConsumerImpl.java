package com.verlumen.tradestream.strategies;

import static com.google.common.base.Preconditions.checkNotNull;

import com.google.inject.Inject;
import com.google.inject.Provider;
import com.google.inject.assistedinject.Assisted;
import com.verlumen.tradestream.marketdata.Candle;
import java.time.Duration;
import java.util.Collections;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.function.Consumer;
import org.apache.kafka.clients.consumer.ConsumerRecords;
import org.apache.kafka.clients.consumer.KafkaConsumer;
import org.apache.kafka.common.errors.WakeupException;

final class MarketDataConsumerImpl implements MarketDataConsumer {
  private static final Duration POLL_TIMEOUT = Duration.ofMillis(100);

  private final Provider<KafkaConsumer<byte[], byte[]>> consumerProvider;
  private final String topic;
  private final ExecutorService executorService;
  private final AtomicBoolean running;
  private KafkaConsumer<byte[], byte[]> consumer;

  @Inject
  MarketDataConsumerImpl(
      Provider<KafkaConsumer<byte[], byte[]>> consumerProvider,
      @Assisted String topic) {
    this.consumerProvider = consumerProvider;
    this.topic = topic;
    this.executorService = Executors.newSingleThreadExecutor();
    this.running = new AtomicBoolean(false);
  }

  @Override
  public void startConsuming(Consumer<Candle> handler) {
    checkNotNull(handler, "Handler cannot be null");
    if (!running.compareAndSet(false, true)) {
      throw new IllegalStateException("Consumer is already running");
    }

    try {
      consumer = consumerProvider.get();
      consumer.subscribe(Collections.singletonList(topic));

      executorService.submit(() -> consumeLoop(handler));
    } catch (Exception e) {
      running.set(false);
      throw new RuntimeException("Failed to start consumer", e);
    }
  }

  @Override
  public void stopConsuming() {
    if (running.compareAndSet(true, false)) {
      if (consumer != null) {
        consumer.wakeup();
      }
      executorService.shutdown();
    }
  }

  private void consumeLoop(Consumer<Candle> handler) {
    try {
      while (running.get()) {
        ConsumerRecords<byte[], byte[]> records = consumer.poll(POLL_TIMEOUT);
        records.forEach(record -> {
          try {
            Candle candle = Candle.parseFrom(record.value());
            handler.accept(candle);
          } catch (Exception e) {
            // Log error but continue processing
          }
        });
      }
    } catch (WakeupException e) {
      // Ignore exception if closing
      if (running.get()) {
        throw e;
      }
    } catch (Exception e) {
      throw new RuntimeException("Error consuming messages", e);
    } finally {
      try {
        consumer.commitSync();
      } catch (Exception e) {
        // Log but proceed with closing
      }
      consumer.close();
    }
  }
}
