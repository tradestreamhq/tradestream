package com.verlumen.tradestream.backtesting;

import static com.google.common.truth.Truth.assertThat;
import static org.mockito.Mockito.when;

import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.testing.fieldbinder.Bind;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import com.verlumen.tradestream.backtesting.GAOptimizationRequest;
import com.verlumen.tradestream.backtesting.GAServiceGrpc;
import com.verlumen.tradestream.backtesting.BestStrategyResponse;
import io.grpc.ManagedChannel;
import io.grpc.inprocess.InProcessServerBuilder;
import io.grpc.inprocess.InProcessChannelBuilder;
import io.grpc.stub.StreamObserver;
import io.grpc.testing.GrpcCleanupRule;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;

@RunWith(JUnit4.class)
public class GAServiceClientImplTest {
  @Rule public final GrpcCleanupRule grpcCleanup = new GrpcCleanupRule();

  private GAServiceGrpc.GAServiceImplBase fakeService =
      new GAServiceGrpc.GAServiceImplBase() {
        @Override
        public void requestOptimization(GAOptimizationRequest request,
                                        StreamObserver<BestStrategyResponse> responseObserver) {
          // Provide a real or fake response
          if (request == null) {
            responseObserver.onError(new NullPointerException("Request is null"));
          } else {
            BestStrategyResponse result = BestStrategyResponse.newBuilder()
                .setBestScore(0.95)
                .build();
            responseObserver.onNext(result);
            responseObserver.onCompleted();
          }
        }
      };

  @Bind GAServiceGrpc.GAServiceBlockingStub stub;

  @Inject
  private GAServiceClientImpl client;

  @Before
  public void setUp() throws Exception {
    String serverName = InProcessServerBuilder.generateName();

    // Build the in-process server with the fakeService
    grpcCleanup.register(
        InProcessServerBuilder.forName(serverName)
            .directExecutor()
            .addService(fakeService)
            .build()
            .start());

    // Create an in-process channel
    ManagedChannel channel = grpcCleanup.register(
        InProcessChannelBuilder.forName(serverName).directExecutor().build());

    // Construct the real stub from the channel
    this.stub = GAServiceGrpc.newBlockingStub(channel);

    // Now inject that realStub into your client
    Guice.createInjector(BoundFieldModule.of(this)).injectMembers(this);
  }

  @Test
  public void requestOptimization_returnsExpectedResult() {
    GAOptimizationRequest request = GAOptimizationRequest.newBuilder().build();
    BestStrategyResponse actual = client.requestOptimization(request);

    // The fakeService returns 0.95
    assertThat(actual.getBestScore()).isWithin(1e-6).of(0.95);
  }
}
