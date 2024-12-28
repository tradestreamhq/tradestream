
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
import io.grpc.inprocess.InProcessServerBuilder;
import io.grpc.inprocess.InProcessChannelBuilder;
import io.grpc.testing.GrpcCleanupRule;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;

@RunWith(JUnit4.class)
public class BacktestServiceClientImplTest {
  @Rule public final GrpcCleanupRule grpcCleanup = new GrpcCleanupRule();

  @Bind private BacktestServiceGrpc.BacktestServiceBlockingStub stub;

  @Inject
  private BacktestServiceClientImpl client;

  @Before
  public void setUp() throws Exception {
    // Create a unique in-process server name.
    String serverName = InProcessServerBuilder.generateName();

    // Build the in-process server with a real or mock service implementation.
    grpcCleanup.register(
        InProcessServerBuilder.forName(serverName)
            .directExecutor()
            // Suppose you have an actual implementation to add:
            .addService(new BacktestServiceGrpc.BacktestServiceImplBase() {
              // Implement the methods you want to test, or use Mockito.spy() if you want partial mocks.
            })
            .build()
            .start());

    // Create a channel connected to the in-process server.
    // The channel is also automatically closed by GrpcCleanupRule
    stub = 
        BacktestServiceGrpc.newBlockingStub(
            grpcCleanup.register(
                InProcessChannelBuilder.forName(serverName).directExecutor().build()));

    Guice.createInjector(BoundFieldModule.of(this)).injectMembers(this);
  }

  @Test
  public void runBacktest_returnsExpectedResult() {
    // ARRANGE
    BacktestRequest request = BacktestRequest.newBuilder().build();
    BacktestResult expected = BacktestResult.newBuilder().setOverallScore(0.85).build();

    // ACT
    BacktestResult actual = client.runBacktest(request);

    // ASSERT
    assertThat(actual).isSameInstanceAs(expected);
  }

  @Test
  public void runBacktest_withNullRequest_throwsException() {
    // ACT + ASSERT
    try {
      client.runBacktest(null);
    } catch (NullPointerException e) {
      assertThat(e).hasMessageThat().contains("Request is null");
    }
  }
}
