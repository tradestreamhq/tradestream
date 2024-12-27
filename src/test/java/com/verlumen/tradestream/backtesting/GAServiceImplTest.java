package com.verlumen.tradestream.backtesting;

import static com.google.common.truth.Truth.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.google.inject.Guice;
import com.google.inject.testing.fieldbinder.Bind;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import com.google.protobuf.Any;
import com.verlumen.tradestream.marketdata.Candle;
import com.verlumen.tradestream.strategies.StrategyType;
import io.grpc.Status;
import io.grpc.StatusRuntimeException;
import io.grpc.stub.StreamObserver;
import java.time.Instant;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.MockitoAnnotations;

@RunWith(JUnit4.class)
public class GAServiceImplTest {
    @Bind
    @Mock
    private GeneticAlgorithmOrchestrator mockOrchestrator;

    @Mock
    private StreamObserver<BestStrategyResponse> mockResponseObserver;

    private GAServiceImpl service;
    private GAOptimizationRequest request;
    private BestStrategyResponse expectedResponse;

    @Before
    public void setUp() {
        MockitoAnnotations.openMocks(this);
        service = new GAServiceImpl(mockOrchestrator);

        // Create standard test request
        request = GAOptimizationRequest.newBuilder()
            .setStrategyType(StrategyType.SMA_RSI)
            .addCandles(createTestCandle())
            .setMaxGenerations(10)
            .setPopulationSize(20)
            .build();

        // Create standard test response
        expectedResponse = BestStrategyResponse.newBuilder()
            .setBestScore(0.85)
            .setBestStrategyParameters(Any.getDefaultInstance())
            .build();
    }

    @Test
    public void requestOptimization_success_completesWithResponse() {
        // Arrange
        when(mockOrchestrator.runOptimization(request))
            .thenReturn(expectedResponse);

        // Act
        service.requestOptimization(request, mockResponseObserver);

        // Assert
        verify(mockResponseObserver).onNext(expectedResponse);
        verify(mockResponseObserver).onCompleted();
    }

    @Test
    public void requestOptimization_orchestratorThrowsException_returnsError() {
        // Arrange
        RuntimeException expectedException = new RuntimeException("Test error");
        when(mockOrchestrator.runOptimization(any()))
            .thenThrow(expectedException);

        // Act
        service.requestOptimization(request, mockResponseObserver);

        // Assert
        ArgumentCaptor<StatusRuntimeException> errorCaptor = 
            ArgumentCaptor.forClass(StatusRuntimeException.class);
        verify(mockResponseObserver).onError(errorCaptor.capture());

        StatusRuntimeException error = errorCaptor.getValue();
        assertThat(error.getStatus().getCode()).isEqualTo(Status.Code.INTERNAL);
        assertThat(error.getMessage()).contains(expectedException.getMessage());
        assertThat(error.getCause()).isEqualTo(expectedException);
    }

    private Candle createTestCandle() {
        return Candle.newBuilder()
            .setTimestamp(Instant.now().toEpochMilli())
            .setOpen(100.0)
            .setHigh(105.0)
            .setLow(95.0)
            .setClose(102.0)
            .setVolume(1000.0)
            .build();
    }
}
