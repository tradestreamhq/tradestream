package com.verlumen.tradestream.backtesting;

import com.google.inject.Inject;
import com.verlumen.tradestream.backtesting.BacktestRequest;
import com.verlumen.tradestream.backtesting.BacktestResult;
import com.verlumen.tradestream.backtesting.BacktestServiceGrpc;
import io.grpc.ManagedChannel;
import io.grpc.ManagedChannelBuilder;

public final class BacktestServiceClientImpl implements BacktestServiceClient {
    private final BacktestServiceGrpc.BacktestServiceBlockingStub stub;

    @Inject
    BacktestServiceClientImpl(ManagedChannel channel) {
        this.stub = BacktestServiceGrpc.newBlockingStub(channel);
    }

    @Override
    public BacktestResult runBacktest(BacktestRequest request) {
        return stub.runBacktest(request);
    }
}
