package com.verlumen.tradestream.backtesting;

import static com.google.common.truth.Truth.assertThat;
import static com.google.protobuf.util.Timestamps.fromMillis;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.marketdata.Candle;
import com.verlumen.tradestream.strategies.SmaRsiParameters;
import com.verlumen.tradestream.strategies.StrategyManager;
import com.verlumen.tradestream.strategies.StrategyType;
import io.grpc.Status;
import io.grpc.StatusRuntimeException;
import io.grpc.stub.StreamObserver;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.MockitoAnnotations;
import org.ta4j.core.BarSeries;
import org.ta4j.core.Strategy;

@RunWith(JUnit4.class)
public class BacktestServiceImplTest {

  @Mock private StrategyManager mockStrategyManager;
  @Mock private BacktestRunner mockBacktestRunner;
  @Mock private Strategy mockStrategy;
  @Mock private StreamObserver<BacktestResult> mockResponseObserver;

  private BacktestServiceImpl service;
  private BacktestRequest request;
  private BacktestResult expectedResult;

  @Before
  public void setUp() throws InvalidProtocolBufferException {
    MockitoAnnotations.openMocks(this);
    service = new BacktestServiceImpl(mockStrategyManager, mockBacktestRunner);

    // Set up default successful mocked responses
    when(mockStrategyManager.createStrategy(any(), any(), any())).thenReturn(mockStrategy);
    when(mockBacktestRunner.runBacktest(any())).thenReturn(createDummyResult());

    // Create a basic valid request
    request = createValidRequest();
    expectedResult = createDummyResult();
  }

  @Test
  public void happyPath_successfulBacktest() throws InvalidProtocolBufferException {
    // Arrange
    when(mockBacktestRunner.runBacktest(any())).thenReturn(expectedResult);

    // Act
    service.runBacktest(request, mockResponseObserver);

    // Assert
    verify(mockResponseObserver).onNext(expectedResult);
    verify(mockResponseObserver).onCompleted();
  }

  @Test
  public void edgeCase_emptyCandles_shouldSucceed() {
    // Arrange
    request =
        BacktestRequest.newBuilder()
            .setStrategyType(StrategyType.SMA_RSI)
            .setStrategyParameters(Any.pack(createValidParameters()))
            .build();

    // Act
    service.runBacktest(request, mockResponseObserver);

    // Assert
    verify(mockResponseObserver).onNext(any());
    verify(mockResponseObserver).onCompleted();
  }

  @Test
  public void edgeCase_singleCandle_shouldSucceed() {
    // Arrange
    request =
        BacktestRequest.newBuilder()
            .setStrategyType(StrategyType.SMA_RSI)
            .setStrategyParameters(Any.pack(createValidParameters()))
            .addCandles(createCandle(1.0))
            .build();

    // Act
    service.runBacktest(request, mockResponseObserver);

    // Assert
    verify(mockResponseObserver).onNext(any());
    verify(mockResponseObserver).onCompleted();
  }

  @Test
  public void error_strategyManagerThrowsException_shouldPropagateError()
      throws InvalidProtocolBufferException {
    // Arrange
    InvalidProtocolBufferException expectedException =
        new InvalidProtocolBufferException("Invalid parameters");
    when(mockStrategyManager.createStrategy(any(), any(), any())).thenThrow(expectedException);

    // Act
    service.runBacktest(request, mockResponseObserver);

    // Assert
    ArgumentCaptor<StatusRuntimeException> captor =
        ArgumentCaptor.forClass(StatusRuntimeException.class);
    verify(mockResponseObserver).onError(captor.capture());

    StatusRuntimeException exception = captor.getValue();
    assertThat(exception.getStatus().getCode()).isEqualTo(Status.Code.INTERNAL);
    assertThat(exception.getStatus().getDescription()).isEqualTo(expectedException.getMessage());
  }

  @Test
  public void error_backtestRunnerThrowsException_shouldPropagateError() {
    // Arrange
    RuntimeException expectedException = new RuntimeException("Backtest failed");
    when(mockBacktestRunner.runBacktest(any())).thenThrow(expectedException);

    // Act
    service.runBacktest(request, mockResponseObserver);

    // Assert
    ArgumentCaptor<StatusRuntimeException> captor =
        ArgumentCaptor.forClass(StatusRuntimeException.class);
    verify(mockResponseObserver).onError(captor.capture());

    StatusRuntimeException exception = captor.getValue();
    assertThat(exception.getStatus().getCode()).isEqualTo(Status.Code.INTERNAL);
    assertThat(exception.getStatus().getDescription()).isEqualTo(expectedException.getMessage());
  }

  @Test
  public void verify_barSeriesCreation() throws InvalidProtocolBufferException {
    // Arrange
    ArgumentCaptor<BacktestRunner.BacktestRequest> captor =
        ArgumentCaptor.forClass(BacktestRunner.BacktestRequest.class);

    // Act
    service.runBacktest(request, mockResponseObserver);

    // Assert
    verify(mockBacktestRunner).runBacktest(captor.capture());
    BacktestRunner.BacktestRequest actualRequest = captor.getValue();
    BarSeries barSeries = actualRequest.barSeries();

    assertThat(barSeries.getBarCount()).isEqualTo(request.getCandlesCount());
    for (int i = 0; i < barSeries.getBarCount(); i++) {
      Candle expectedCandle = request.getCandles(i);
      assertThat(barSeries.getBar(i).getClosePrice().doubleValue())
          .isEqualTo(expectedCandle.getClose());
      assertThat(barSeries.getBar(i).getOpenPrice().doubleValue())
          .isEqualTo(expectedCandle.getOpen());
      assertThat(barSeries.getBar(i).getHighPrice().doubleValue())
          .isEqualTo(expectedCandle.getHigh());
      assertThat(barSeries.getBar(i).getLowPrice().doubleValue())
          .isEqualTo(expectedCandle.getLow());
      assertThat(barSeries.getBar(i).getVolume().doubleValue())
          .isEqualTo(expectedCandle.getVolume());
    }
  }

  private BacktestRequest createValidRequest() {
    return BacktestRequest.newBuilder()
        .setStrategyType(StrategyType.SMA_RSI)
        .setStrategyParameters(Any.pack(createValidParameters()))
        .addAllCandles(createTestCandles())
        .build();
  }

  private SmaRsiParameters createValidParameters() {
    return SmaRsiParameters.newBuilder()
        .setRsiPeriod(14)
        .setMovingAveragePeriod(14)
        .setOverboughtThreshold(70)
        .setOversoldThreshold(30)
        .build();
  }

  private List<Candle> createTestCandles() {
    List<Candle> candles = new ArrayList<>();
    for (int i = 0; i < 10; i++) {
      candles.add(createCandle(i + 1.0));
    }
    return candles;
  }

  private Candle createCandle(double price) {
    long epochMillis = Instant.now().toEpochMilli();
    return Candle.newBuilder()
        .setTimestamp(fromMillis(epochMillis))
        .setOpen(price)
        .setHigh(price + 1)
        .setLow(price - 1)
        .setClose(price)
        .setVolume(1000)
        .build();
  }

  private BacktestResult createDummyResult() {
    return BacktestResult.newBuilder().setOverallScore(0.75).build();
  }
}
