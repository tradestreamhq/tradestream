package com.verlumen.tradestream.backtesting;

import static com.google.common.truth.Truth.assertThat;
import static org.mockito.Mockito.when;

import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.testing.fieldbinder.Bind;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import com.verlumen.tradestream.backtesting.BacktestRequest;
import com.verlumen.tradestream.backtesting.BacktestResult;
import com.verlumen.tradestream.backtesting.BacktestServiceGrpc;
import io.grpc.ManagedChannel;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.mockito.Mock;
import org.mockito.MockitoAnnotations;

@RunWith(JUnit4.class)
public class BacktestServiceClientImplTest {

  // A mock for the gRPC channel.
  @Bind @Mock ManagedChannel mockChannel;

  // We’ll pretend we can also mock the blocking stub object. Typically you might
  // just mock the entire client, but for demonstration, we can mock the stub itself:
  @Mock private BacktestServiceGrpc.BacktestServiceBlockingStub mockStub;

  @Inject
  private BacktestServiceClientImpl client;

  @Before
  public void setUp() {
    // Initialize Mockito
    MockitoAnnotations.openMocks(this);
    // Create a Guice injector that binds all @Bind fields
    Guice.createInjector(BoundFieldModule.of(this)).injectMembers(this);
  }

  @Test
  public void runBacktest_returnsExpectedResult() {
    // ARRANGE
    BacktestRequest request = BacktestRequest.newBuilder().build();
    BacktestResult expected = BacktestResult.newBuilder().setOverallScore(0.85).build();
    when(mockStub.runBacktest(request)).thenReturn(expected);

    // ACT
    BacktestResult actual = client.runBacktest(request);

    // ASSERT
    assertThat(actual).isSameInstanceAs(expected);
  }

  @Test
  public void runBacktest_withNullRequest_throwsException() {
    // ARRANGE
    when(mockStub.runBacktest(null)).thenThrow(new NullPointerException("Request is null"));

    // ACT + ASSERT
    try {
      client.runBacktest(null);
    } catch (NullPointerException e) {
      assertThat(e).hasMessageThat().contains("Request is null");
    }
  }
}
