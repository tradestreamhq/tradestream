package com.verlumen.tradestream.pipeline;

import com.google.auto.value.AutoValue;
import com.google.inject.AbstractModule;
import com.google.inject.Provides;
import com.verlumen.tradestream.backtesting.BacktestingModule;
import com.verlumen.tradestream.discovery.DiscoveryModule;
import com.verlumen.tradestream.execution.RunMode;
import com.verlumen.tradestream.http.HttpModule;
import com.verlumen.tradestream.influxdb.InfluxDbModule;
import com.verlumen.tradestream.marketdata.FillForwardCandles;
import com.verlumen.tradestream.marketdata.MarketDataModule;
import com.verlumen.tradestream.marketdata.TradeToCandle;
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
    install(BacktestingModule.create());
    install(new DiscoveryModule());
    install(HttpModule.create());
    install(new InfluxDbModule(influxDbUrl(), influxDbToken(), influxDbOrg(), influxDbBucket()));
    install(InstrumentsModule.create(runMode(), coinMarketCapApiKey(), topCurrencyCount()));
    install(KafkaModule.create(bootstrapServers()));
    install(MarketDataModule.create(exchangeName(), candleDuration(), runMode(), tiingoApiKey()));
    install(SignalsModule.create(signalTopic()));
    install(StrategiesModule.create());
    install(Ta4jModule.create());
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
