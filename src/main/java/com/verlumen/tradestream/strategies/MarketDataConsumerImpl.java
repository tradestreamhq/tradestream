package com.verlumen.tradestream.strategies;

import static com.google.common.base.Preconditions.checkNotNull;

import com.google.inject.Inject;
import com.google.inject.Provider;
import com.google.inject.assistedinject.Assisted;
import com.verlumen.tradestream.marketdata.Candle;
import java.time.Duration;
import java.util.Collections;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Future;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.function.Consumer;
import org.apache.kafka.clients.consumer.ConsumerRecords;
import org.apache.kafka.clients.consumer.KafkaConsumer;
import org.apache.kafka.common.errors.WakeupException;

/**
 * Consumes candle data from a Kafka topic using the Kafka Consumer API.
 * Supports graceful shutdown and error handling.
 */
final class MarketDataConsumerImpl implements MarketDataConsumer {
  private static final Duration POLL_TIMEOUT = Duration.ofMillis(100);

  private final Provider<KafkaConsumer<byte[], byte[]>> consumerProvider;
  private final String topic;
  private final ExecutorService executorService;
  private final AtomicBoolean running;
  private KafkaConsumer<byte[], byte[]> consumer;
  private Future<?> consumerTask;

  @Inject
  MarketDataConsumerImpl(
      Provider<KafkaConsumer<byte[], byte[]>> consumerProvider,
      ExecutorService executorService,
      @Assisted String topic) {
    this.consumerProvider = consumerProvider;
    this.executorService = executorService;
    this.topic = topic;
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

      consumerTask = executorService.submit(() -> consumeLoop(handler));
    } catch (Exception e) {
      running.set(false);
      if (consumer != null) {
        consumer.close();
      }
      throw new RuntimeException("Failed to start consumer", e);
    }
  }

  @Override
  public void stopConsuming() {
    if (running.compareAndSet(true, false)) {
      if (consumer != null) {
        consumer.wakeup();
      }
      if (consumerTask != null) {
        consumerTask.cancel(true);
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
        if (consumer != null) {
          consumer.commitSync();
          consumer.close();
        }
      } catch (Exception e) {
        // Log but proceed with closing
      }
    }
  }
}
