package com.verlumen.tradestream.strategies;

import static com.google.common.base.Preconditions.checkNotNull;

import com.google.common.flogger.FluentLogger;
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
  private static final FluentLogger logger = FluentLogger.forEnclosingClass();
  private static final Duration DEFAULT_POLL_TIMEOUT = Duration.ofMillis(100);

  private final Provider<KafkaConsumer<byte[], byte[]>> consumer;
  private final String topic;
  private final ExecutorService executorService;
  private final AtomicBoolean running;

  @Inject
  MarketDataConsumerImpl(
      Provider<KafkaConsumer<byte[], byte[]>> consumerProvider,
      @Assisted String topic
  ) {
    this.consumer = consumerProvider;
    this.topic = topic;
    this.executorService = Executors.newSingleThreadExecutor();
    this.running = new AtomicBoolean(false);
  }

  @Override
  public void start(Consumer<Candle> handler) {
    checkNotNull(handler, "Handler cannot be null");
    if (!running.compareAndSet(false, true)) {
      throw new IllegalStateException("Consumer is already running");
    }

    try {
      consumer.subscribe(Collections.singletonList(topic));
      logger.atInfo().log("Subscribed to Kafka topic: %s", topic);

      executorService.submit(() -> consumeLoop(handler));
      logger.atInfo().log("MarketDataConsumer started on topic: %s", topic);
    } catch (Exception e) {
      running.set(false);
      logger.atSevere().withCause(e).log("Failed to start consumer on topic: %s", topic);
      throw new RuntimeException("Failed to start consumer", e);
    }
  }

  private void consumeLoop(Consumer<Candle> handler) {
    try {
      while (running.get()) {
        ConsumerRecords<byte[], byte[]> records = consumer.poll(DEFAULT_POLL_TIMEOUT);
        records.forEach(record -> {
          try {
            Candle candle = Candle.parseFrom(record.value());
            handler.accept(candle);
          } catch (Exception ex) {
            logger.atWarning().withCause(ex)
                  .log("Error processing message from partition %d offset %d",
                       record.partition(), record.offset());
          }
        });
      }
    } catch (WakeupException we) {
      if (running.get()) {
        // Unexpected wakeup
        logger.atSevere().withCause(we).log("Unexpected wakeup exception");
        throw we;
      }
      // else: ignore wakeup if we are shutting down
    } catch (Exception e) {
      logger.atSevere().withCause(e)
            .log("Error consuming messages on topic %s", topic);
      throw new RuntimeException("Consumer loop failed", e);
    } finally {
      try {
        consumer.commitSync();  // or consider commitAsync() if consistent with the codebase
      } catch (Exception ce) {
        logger.atWarning().withCause(ce).log("Error committing final offsets");
      }
      consumer.close();
      logger.atInfo().log("Kafka consumer closed for topic: %s", topic);
    }
  }

  @Override
  public void stop() {
    if (running.compareAndSet(true, false)) {
      logger.atInfo().log("Stopping MarketDataConsumer for topic: %s", topic);
      try {
        consumer.wakeup(); // triggers WakeupException in consumeLoop
        executorService.shutdown();
        // (Optionally) await termination here if needed
      } catch (Exception e) {
        logger.atWarning().withCause(e).log("Error stopping MarketDataConsumer for topic: %s", topic);
      }
    }
  }
}
