package com.verlumen.tradestream.pipeline;

import com.google.auto.value.AutoValue;
import com.google.inject.AbstractModule;
import com.google.inject.Provides;
import com.verlumen.tradestream.backtesting.BacktestingModule;
import com.verlumen.tradestream.discovery.DiscoveryModule;
import com.verlumen.tradestream.execution.RunMode;
import com.verlumen.tradestream.http.HttpModule;
import com.verlumen.tradestream.influxdb.InfluxDbModule;
import com.verlumen.tradestream.instruments.InstrumentsModule;
import com.verlumen.tradestream.kafka.KafkaModule;
import com.verlumen.tradestream.marketdata.MarketDataModule;
import com.verlumen.tradestream.marketdata.FillForwardCandles;
import com.verlumen.tradestream.postgres.PostgresModule;
import com.verlumen.tradestream.signals.SignalsModule;
import com.verlumen.tradestream.strategies.StrategiesModule;
import com.verlumen.tradestream.ta4j.Ta4jModule;
import org.joda.time.Duration;

@AutoValue
abstract class PipelineModule extends AbstractModule {
    abstract String exchangeName();
    abstract Duration candleDuration();
    abstract RunMode runMode();
    abstract String tiingoApiKey();
    abstract String coinMarketCapApiKey();
    abstract int topCurrencyCount();
    abstract String signalTopic();
    abstract String influxDbUrl();
    abstract String influxDbToken();
    abstract String influxDbOrg();
    abstract String influxDbBucket();
    abstract String bootstrapServers();
    abstract int maxForwardIntervals();

    static PipelineModule create(
        String exchangeName,
        Duration candleDuration,
        RunMode runMode,
        String tiingoApiKey,
        String coinMarketCapApiKey,
        int topCurrencyCount,
        String signalTopic,
        String influxDbUrl,
        String influxDbToken,
        String influxDbOrg,
        String influxDbBucket,
        String bootstrapServers,
        int maxForwardIntervals) {
        return new AutoValue_PipelineModule(
            exchangeName,
            candleDuration,
            runMode,
            tiingoApiKey,
            coinMarketCapApiKey,
            topCurrencyCount,
            signalTopic,
            influxDbUrl,
            influxDbToken,
            influxDbOrg,
            influxDbBucket,
            bootstrapServers,
            maxForwardIntervals);
    }

    @Override
    protected void configure() {
        install(new BacktestingModule());
        install(new DiscoveryModule());
        install(HttpModule.create());
        install(new InfluxDbModule(influxDbUrl(), influxDbToken(), influxDbOrg(), influxDbBucket()));
        install(InstrumentsModule.create(runMode(), coinMarketCapApiKey(), topCurrencyCount()));
        install(KafkaModule.create(bootstrapServers()));
        install(MarketDataModule.create(exchangeName(), candleDuration(), runMode(), tiingoApiKey()));
        install(new PostgresModule());
        install(SignalsModule.create(signalTopic()));
        install(new StrategiesModule());
        install(Ta4jModule.create());
    }

    @Provides
    FillForwardCandles provideFillForwardCandles(FillForwardCandles.Factory factory) {
        return factory.create(candleDuration(), maxForwardIntervals());
    }
}
