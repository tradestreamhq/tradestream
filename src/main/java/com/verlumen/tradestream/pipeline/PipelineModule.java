package com.verlumen.tradestream.pipeline;

import static com.google.protobuf.util.Timestamps.fromMillis;

import com.google.auto.value.AutoValue;
import com.google.common.collect.ImmutableList;
import com.google.inject.AbstractModule;
import com.google.inject.Provider;
import com.google.inject.Provides;
import com.google.inject.Singleton;
import com.verlumen.tradestream.backtesting.BacktestingModule;
import com.verlumen.tradestream.discovery.ProdDiscoveryModule;
import com.verlumen.tradestream.execution.RunMode;
import com.verlumen.tradestream.http.HttpModule;
import com.verlumen.tradestream.influxdb.InfluxDbModule;
import com.verlumen.tradestream.instruments.InstrumentsModule;
import com.verlumen.tradestream.kafka.KafkaModule;
import com.verlumen.tradestream.marketdata.CandleSource;
import com.verlumen.tradestream.marketdata.DryRunTradeSource;
import com.verlumen.tradestream.marketdata.FillForwardCandles;
import com.verlumen.tradestream.marketdata.MarketDataModule;
import com.verlumen.tradestream.marketdata.TiingoCryptoCandleSource;
import com.verlumen.tradestream.marketdata.Trade;
import com.verlumen.tradestream.marketdata.TradeBackedCandleSource;
import com.verlumen.tradestream.marketdata.TradeSource;
import com.verlumen.tradestream.marketdata.TradeToCandle;
import com.verlumen.tradestream.postgres.PostgresModule;
import com.verlumen.tradestream.signals.SignalsModule;
import com.verlumen.tradestream.strategies.StrategiesModule;
import com.verlumen.tradestream.ta4j.Ta4jModule;
import org.joda.time.Duration;

@AutoValue
abstract class PipelineModule extends AbstractModule {
  static PipelineModule create(
      String bootstrapServers,
      int candleDurationMinutes,
      String coinMarketCapApiKey,
      String exchangeName,
      int maxForwardIntervals,
      RunMode runMode,
      String signalTopic,
      int topCurrencyCount,
      String tiingoApiKey,
      String influxDbUrl,
      String influxDbToken,
      String influxDbOrg,
      String influxDbBucket) {
    return new AutoValue_PipelineModule(
        bootstrapServers,
        Duration.standardMinutes(candleDurationMinutes),
        coinMarketCapApiKey,
        exchangeName,
        maxForwardIntervals,
        runMode,
        signalTopic,
        topCurrencyCount,
        tiingoApiKey,
        influxDbUrl,
        influxDbToken,
        influxDbOrg,
        influxDbBucket);
  }

  abstract String bootstrapServers();

  abstract Duration candleDuration();

  abstract String coinMarketCapApiKey();

  abstract String exchangeName();

  abstract int maxForwardIntervals();

  abstract RunMode runMode();

  abstract String signalTopic();

  abstract int topCurrencyCount();

  abstract String tiingoApiKey();

  abstract String influxDbUrl();

  abstract String influxDbToken();

  abstract String influxDbOrg();

  abstract String influxDbBucket();

  @Override
  protected void configure() {
    install(new BacktestingModule());
    install(new ProdDiscoveryModule());
    install(HttpModule.create());
    install(new InfluxDbModule(influxDbUrl(), influxDbToken(), influxDbOrg(), influxDbBucket()));
    install(InstrumentsModule.create(runMode(), coinMarketCapApiKey(), topCurrencyCount()));
    install(KafkaModule.create(bootstrapServers()));
    install(MarketDataModule.create()); // No parameters needed anymore
    install(new PostgresModule());
    install(SignalsModule.create(signalTopic()));
    install(new StrategiesModule());
    install(Ta4jModule.create());
  }

  @Provides
  @Singleton
  CandleSource provideCandleSource(
      Provider<TradeBackedCandleSource> tradeBackedCandleSource,
      TiingoCryptoCandleSource.Factory tiingoCryptoCandleSourceFactory) {
    switch (runMode()) {
      case DRY:
        return tradeBackedCandleSource.get();
      case WET:
        return tiingoCryptoCandleSourceFactory.create(candleDuration(), tiingoApiKey());
      default:
        throw new UnsupportedOperationException("Unsupported RunMode: " + runMode());
    }
  }

  @Provides
  @Singleton
  TradeSource provideTradeSource() {
    switch (runMode()) {
      case DRY:
        return DryRunTradeSource.create(
            ImmutableList.of(
                Trade.newBuilder()
                    .setExchange(exchangeName())
                    .setCurrencyPair("DRY/RUN")
                    .setTradeId("trade-123")
                    .setTimestamp(fromMillis(1259999L))
                    .setPrice(50000.0)
                    .setVolume(0.1)
                    .build()));
      default:
        throw new UnsupportedOperationException("Unsupported RunMode: " + runMode());
    }
  }

  @Provides
  FillForwardCandles provideFillForwardCandles(FillForwardCandles.Factory factory) {
    return factory.create(candleDuration(), maxForwardIntervals());
  }

  @Provides
  TimingConfig provideTimingConfig() {
    return TimingConfig.create();
  }

  @Provides
  TradeToCandle provideTradeToCandle(TradeToCandle.Factory factory) {
    return factory.create(candleDuration());
  }
}
