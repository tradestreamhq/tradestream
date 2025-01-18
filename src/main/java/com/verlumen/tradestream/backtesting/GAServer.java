package com.verlumen.tradestream.backtesting;

import com.google.common.flogger.FluentLogger;
import com.google.inject.Guice;
import com.google.inject.Injector;
import io.grpc.Server;
import io.grpc.ServerBuilder;

public class GAServer {
    private static final FluentLogger logger = FluentLogger.forEnclosingClass();
    public static void main(String[] args) throws Exception {
        // Create Guice injector
        Injector injector = Guice.createInjector(BacktestingModule.create());

        // Get GAServiceImpl instance from Guice
        GAServiceImpl gaService = injector.getInstance(GAServiceImpl.class);

        // Create and start gRPC server
        Server server = ServerBuilder.forPort(50051)
            .addService(gaService)
            .build();

        server.start();
        System.out.println("GA Server started on port 50051");

        // Keep server running
        server.awaitTermination();
    }
}
