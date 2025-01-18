package com.verlumen.tradestream.grpc;

import io.grpc.ManagedChannel;
import io.grpc.ManagedChannelBuilder;

public record Endpoint(String host, String port) {
  public ManagedChannel createChannel() {
    return ManagedChannelBuilder.forAddress(
        .forAddress(host, port)
        .usePlaintext()
        .build();
  }
}
