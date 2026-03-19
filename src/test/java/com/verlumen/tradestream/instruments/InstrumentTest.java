package com.verlumen.tradestream.instruments;

import static com.google.common.truth.Truth.assertThat;
import static org.junit.Assert.assertThrows;

import com.verlumen.tradestream.marketdata.AssetClass;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;

@RunWith(JUnit4.class)
public class InstrumentTest {

  @Test
  public void create_returnsInstrumentWithGivenFields() {
    Instrument instrument = Instrument.create("BTC/USD", AssetClass.CRYPTO);
    assertThat(instrument.symbol()).isEqualTo("BTC/USD");
    assertThat(instrument.assetClass()).isEqualTo(AssetClass.CRYPTO);
  }

  @Test
  public void fromCurrencyPair_returnsCryptoInstrument() {
    CurrencyPair pair = CurrencyPair.fromSymbol("BTC/USD");
    Instrument instrument = Instrument.fromCurrencyPair(pair);
    assertThat(instrument.symbol()).isEqualTo("BTC/USD");
    assertThat(instrument.assetClass()).isEqualTo(AssetClass.CRYPTO);
  }

  @Test
  public void stock_returnsStockInstrument() {
    Instrument instrument = Instrument.stock("aapl");
    assertThat(instrument.symbol()).isEqualTo("AAPL");
    assertThat(instrument.assetClass()).isEqualTo(AssetClass.STOCKS);
  }

  @Test
  public void forex_returnsForexInstrument() {
    Instrument instrument = Instrument.forex("eur/usd");
    assertThat(instrument.symbol()).isEqualTo("EUR/USD");
    assertThat(instrument.assetClass()).isEqualTo(AssetClass.FOREX);
  }

  @Test
  public void commodity_returnsCommodityInstrument() {
    Instrument instrument = Instrument.commodity("wti");
    assertThat(instrument.symbol()).isEqualTo("WTI");
    assertThat(instrument.assetClass()).isEqualTo(AssetClass.COMMODITIES);
  }

  @Test
  public void toCurrencyPair_withValidPair_succeeds() {
    Instrument instrument = Instrument.forex("EUR/USD");
    CurrencyPair pair = instrument.toCurrencyPair();
    assertThat(pair.base().symbol()).isEqualTo("EUR");
    assertThat(pair.counter().symbol()).isEqualTo("USD");
  }

  @Test
  public void toCurrencyPair_withSingleSymbol_throws() {
    Instrument instrument = Instrument.stock("AAPL");
    assertThrows(IllegalArgumentException.class, instrument::toCurrencyPair);
  }
}
