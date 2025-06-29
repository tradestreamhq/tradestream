package com.verlumen.tradestream.instruments;

import static com.google.common.truth.Truth.assertThat;
import static org.junit.Assert.assertThrows;

import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;

@RunWith(JUnit4.class)
public class CurrencyPairTest {
  @Test
  public void fromSymbol_forwardSlashDelimiter_success() {
    // Arrange
    String symbol = "EUR/USD";

    // Act
    CurrencyPair currencyPair = CurrencyPair.fromSymbol(symbol);

    // Assert
    assertThat(currencyPair.base()).isEqualTo(Currency.create("EUR"));
  }

  @Test
  public void fromSymbol_forwardSlashDelimiter_success_counter() {
    // Arrange
    String symbol = "EUR/USD";

    // Act
    CurrencyPair currencyPair = CurrencyPair.fromSymbol(symbol);

    // Assert
    assertThat(currencyPair.counter()).isEqualTo(Currency.create("USD"));
  }

  @Test
  public void fromSymbol_hyphenDelimiter_success() {
    // Arrange
    String symbol = "BTC-ETH";

    // Act
    CurrencyPair currencyPair = CurrencyPair.fromSymbol(symbol);

    // Assert
    assertThat(currencyPair.base()).isEqualTo(Currency.create("BTC"));
  }

  @Test
  public void fromSymbol_hyphenDelimiter_success_counter() {
    // Arrange
    String symbol = "BTC-ETH";

    // Act
    CurrencyPair currencyPair = CurrencyPair.fromSymbol(symbol);

    // Assert
    assertThat(currencyPair.counter()).isEqualTo(Currency.create("ETH"));
  }

  @Test
  public void fromSymbol_mixedCase_success() {
    // Arrange
    String symbol = "eUr/UsD";

    // Act
    CurrencyPair currencyPair = CurrencyPair.fromSymbol(symbol);

    // Assert
    assertThat(currencyPair.base()).isEqualTo(Currency.create("EUR"));
  }

  @Test
  public void fromSymbol_mixedCase_success_counter() {
    // Arrange
    String symbol = "eUr/UsD";

    // Act
    CurrencyPair currencyPair = CurrencyPair.fromSymbol(symbol);

    // Assert
    assertThat(currencyPair.counter()).isEqualTo(Currency.create("USD"));
  }

  @Test
  public void fromSymbol_extraSpaces_success() {
    // Arrange
    String symbol = "  EUR  /   USD  ";

    // Act
    CurrencyPair currencyPair = CurrencyPair.fromSymbol(symbol);

    // Assert
    assertThat(currencyPair.base()).isEqualTo(Currency.create("EUR"));
  }

  @Test
  public void fromSymbol_extraSpaces_success_counter() {
    // Arrange
    String symbol = "  EUR  /   USD  ";

    // Act
    CurrencyPair currencyPair = CurrencyPair.fromSymbol(symbol);

    // Assert
    assertThat(currencyPair.counter()).isEqualTo(Currency.create("USD"));
  }

  @Test
  public void fromSymbol_invalidDelimiter_throwsIllegalArgumentException() {
    // Arrange
    String symbol = "EUR.USD";

    // Act & Assert
    assertThrows(IllegalArgumentException.class, () -> CurrencyPair.fromSymbol(symbol));
  }

  @Test
  public void fromSymbol_ambiguousDelimiter_throwsIllegalArgumentException() {
    // Arrange
    String symbol = "EUR/USD-GBP";

    // Act & Assert
    assertThrows(IllegalArgumentException.class, () -> CurrencyPair.fromSymbol(symbol));
  }

  @Test
  public void fromSymbol_missingBaseCurrency_throwsIllegalArgumentException() {
    // Arrange
    String symbol = "/USD";

    // Act & Assert
    assertThrows(IllegalArgumentException.class, () -> CurrencyPair.fromSymbol(symbol));
  }

  @Test
  public void fromSymbol_missingCounterCurrency_throwsIllegalArgumentException() {
    // Arrange
    String symbol = "EUR/";

    // Act & Assert
    assertThrows(IllegalArgumentException.class, () -> CurrencyPair.fromSymbol(symbol));
  }

  @Test
  public void fromSymbol_duplicateCurrencies_throwsIllegalArgumentException() {
    // Arrange
    String symbol = "EUR/EUR";

    // Act & Assert
    assertThrows(IllegalArgumentException.class, () -> CurrencyPair.fromSymbol(symbol));
  }
}
