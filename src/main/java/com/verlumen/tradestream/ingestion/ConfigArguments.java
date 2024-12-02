package com.verlumen.tradestream.ingestion;

import com.google.auto.value.AutoValue;
import com.google.common.collect.ImmutableList;
import com.google.inject.Provider;
import net.sourceforge.argparse4j.ArgumentParsers;
import net.sourceforge.argparse4j.inf.ArgumentParser;
import net.sourceforge.argparse4j.inf.ArgumentParserException;
import net.sourceforge.argparse4j.inf.Namespace;

@AutoValue
abstract class ConfigArguments implements Provider<Namespace> {
  private static final String API_KEY_ENV_VAR = "TRADESTREAM_COINMARKETCAP_API_KEY";

  static ConfigArguments create(ImmutableList<String> args) {
    return new AutoValue_ConfigArguments(args);
  }

  abstract ImmutableList<String> args();

  @Override
  public Namespace get() {
    try {
      return createParser().parseArgs(args().toArray(new String[0]));
    } catch (ArgumentParserException e) {
      throw new RuntimeException("Unable to parse arguments.", e);
    }
  }

  private static ArgumentParser createParser() {
    ArgumentParser parser = ArgumentParsers.newFor("TradeStreamDataIngestion")
      .build()
      .defaultHelp(true)
      .description("Configuration for Kafka producer and exchange settings");

    // Existing arguments
    parser.addArgument("--candleIntervalSeconds")
      .type(Integer.class)
      .setDefault(60)
      .help("Candle interval in seconds");

    parser.addArgument("--candlePublisherTopic")
      .setDefault("candles") 
      .help("Kafka topic to publish candle data");

    // Kafka configuration
    parser.addArgument("--kafka.bootstrap.servers")
      .setDefault("localhost:9092")
      .help("Kafka bootstrap servers");

    parser.addArgument("--kafka.acks")
      .setDefault("all")
      .help("Kafka acknowledgment configuration");

    parser.addArgument("--kafka.retries")
      .type(Integer.class)
      .setDefault(0)
      .help("Number of retries");

    parser.addArgument("--kafka.batch.size")
      .type(Integer.class)
      .setDefault(16384)
      .help("Batch size in bytes");

    parser.addArgument("--kafka.linger.ms")
      .type(Integer.class)
      .setDefault(1)
      .help("Linger time in milliseconds");

    parser.addArgument("--kafka.buffer.memory")
      .type(Integer.class)
      .setDefault(33554432)
      .help("Buffer memory in bytes");

    parser.addArgument("--kafka.key.serializer")
      .setDefault("org.apache.kafka.common.serialization.StringSerializer")
      .help("Key serializer class");

    parser.addArgument("--kafka.value.serializer")
      .setDefault("org.apache.kafka.common.serialization.StringSerializer")
      .help("Value serializer class");

    // Exchange configuration
    parser.addArgument("--xchange.exchangeName")
      .setDefault("info.bitrich.xchangestream.coinbasepro.CoinbaseProStreamingExchange")
      .help("Exchange name");

    // CoinMarketCap configuration
    parser.addArgument("--coinmarketcap.apiKey")
      .setDefault(System.getenv(API_KEY_ENV_VAR))
      .help("CoinMarketCap API Key (default: value of TRADESTREAM_COINMARKETCAP_API_KEY environment variable)");

    parser.addArgument("--coinmarketcap.topN")
      .type(Integer.class)
      .setDefault(100)
      .help("Number of top cryptocurrencies to track (default: 100)");

    // Run mode configuration
    parser.addArgument("--runMode")
      .choices("wet", "dry")
      .setDefault("wet")
      .help("Run mode: wet or dry");

    return parser;
  }
}
