package com.verlumen.tradestream.ingestion;

import static com.google.common.collect.ImmutableList.toImmutableList;
import static com.google.common.collect.ImmutableSet.toImmutableSet;
import static com.google.common.collect.Sets.difference;
import static com.google.common.collect.Sets.intersection;

import com.google.common.collect.ImmutableList;
import com.google.common.collect.ImmutableSet;
import com.google.common.flogger.FluentLogger;
import com.google.inject.Inject;
import com.google.inject.Provider;
import com.verlumen.tradestream.instruments.CurrencyPair;
import com.verlumen.tradestream.instruments.CurrencyPairSupply;
import com.verlumen.tradestream.marketdata.Trade;
import com.verlumen.tradestream.marketdata.ExchangeStreamingClient;
import com.verlumen.tradestream.marketdata.TradePublisher;
import java.util.Objects;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.Executors;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.TimeUnit;
import java.util.stream.Stream;

final class RealTimeDataIngestionImpl implements RealTimeDataIngestion {
  private static final FluentLogger logger = FluentLogger.forEnclosingClass();

  private final Provider<CurrencyPairSupply> currencyPairSupply;
  private final ExchangeStreamingClient exchangeClient;
  private final TradePublisher tradePublisher;

  // Blocking queue to store incoming trades
  private final BlockingQueue<Trade> tradeQueue = new LinkedBlockingQueue<>();
  // Executor to run the trade publishing task
  private ExecutorService tradePublisherExecutor;

  @Inject
  RealTimeDataIngestionImpl(
      Provider<CurrencyPairSupply> currencyPairSupply,
      ExchangeStreamingClient exchangeClient,
      TradePublisher tradePublisher) {
    this.currencyPairSupply = currencyPairSupply;
    this.exchangeClient = exchangeClient;
    this.tradePublisher = tradePublisher;
  }

  @Override
  public void start() {
    logger.atInfo().log(
        "Starting real-time data ingestion for %s", exchangeClient.getExchangeName());

    // Start streaming and push incoming trades into the blocking queue.
    exchangeClient.startStreaming(supportedCurrencyPairs(), trade -> {
      try {
        tradeQueue.put(trade);
      } catch (InterruptedException e) {
        Thread.currentThread().interrupt();
        logger.atWarning().withCause(e).log("Interrupted while adding trade to queue");
      }
    });

    // Start a background task to read from the blocking queue and publish trades.
    tradePublisherExecutor = Executors.newSingleThreadExecutor();
    tradePublisherExecutor.submit(() -> 
      // Use stream.generate to continuously take trades from the queue.
      Stream.generate(() -> {
          try {
            return tradeQueue.take(); // This call blocks until a trade is available.
          } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            return null; // Returning null signals termination.
          }
        })
        .takeWhile(Objects::nonNull) // Stop processing if a null is encountered.
        .forEach(tradePublisher::publishTrade)
    );

    logger.atInfo().log("Real-time data ingestion system fully initialized and running");
  }

  @Override
  public void shutdown() {
    logger.atInfo().log("Beginning shutdown sequence...");

    logger.atInfo().log("Stopping exchange streaming...");
    exchangeClient.stopStreaming();

    logger.atInfo().log("Shutting down trade publisher executor...");
    if (tradePublisherExecutor != null) {
      // Shut down the executor service and wait for the publishing task to finish.
      tradePublisherExecutor.shutdownNow();
      try {
        if (!tradePublisherExecutor.awaitTermination(10, TimeUnit.SECONDS)) {
          logger.atWarning().log("Trade publisher executor did not terminate in time.");
        }
      } catch (InterruptedException e) {
        Thread.currentThread().interrupt();
        logger.atWarning().withCause(e).log("Interrupted while waiting for trade publisher executor shutdown");
      }
    }

    logger.atInfo().log("Closing trade publisher...");
    try {
      tradePublisher.close();
      logger.atInfo().log("Successfully closed trade publisher");
    } catch (Exception e) {
      logger.atWarning().withCause(e).log("Error closing trade publisher");
    }

    logger.atInfo().log("Shutdown sequence complete");
  }

  private ImmutableList<CurrencyPair> supportedCurrencyPairs() {
    ImmutableSet<CurrencyPair> supportedPairs =
        ImmutableSet.copyOf(exchangeClient.supportedCurrencyPairs());
    ImmutableSet<CurrencyPair> requestedPairs =
        ImmutableSet.copyOf(currencyPairSupply.get().currencyPairs());
    difference(requestedPairs, supportedPairs)
        .forEach(
            unsupportedPair ->
                logger.atInfo().log(
                    "Pair with symbol %s is not supported.", unsupportedPair.symbol()));
    return intersection(requestedPairs, supportedPairs).immutableCopy().asList();
  }
}
