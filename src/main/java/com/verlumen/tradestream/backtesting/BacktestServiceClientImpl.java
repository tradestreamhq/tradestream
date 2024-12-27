package com.verlumen.tradestream.backtesting;

import com.verlumen.tradestream.backtesting.BacktestRequest;
import com.verlumen.tradestream.backtesting.BacktestResult;
import com.verlumen.tradestream.backtesting.BacktestServiceGrpc;
import io.grpc.ManagedChannel;
import io.grpc.ManagedChannelBuilder;

public final class BacktestServiceClientImpl implements BacktestServiceClient {
    private final BacktestServiceGrpc.BacktestServiceBlockingStub stub;

    /**
     * Constructs a client that uses the provided gRPC channel.
     */
    public BacktestServiceClientImpl(ManagedChannel channel) {
        this.stub = BacktestServiceGrpc.newBlockingStub(channel);
    }

    /**
     * Optionally provide a convenience constructor
     * that builds the channel internally.
     */
    public BacktestServiceClientImpl(String target) {
        this(ManagedChannelBuilder.forTarget(target)
            .usePlaintext()
            .build());
    }

    @Override
    public BacktestResult runBacktest(BacktestRequest request) {
        // Plain blocking call to the server
        return stub.runBacktest(request);
    }
}
