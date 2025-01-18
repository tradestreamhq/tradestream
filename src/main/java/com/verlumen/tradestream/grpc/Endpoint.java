package com.verlumen.tradestream.grpc;

import io.grpc.ManagedChannel;
import io.grpc.ManagedChannelBuilder;

public record Endpoint(String host, int port) {
  public ManagedChannel createChannel() {
    return ManagedChannelBuilder
        .forAddress(host, port)
        .usePlaintext()
        .build();
  }
}
