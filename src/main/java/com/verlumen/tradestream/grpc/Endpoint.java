package com.verlumen.tradestream.grpc;

import io.grpc.ManagedChannel;
import io.grpc.ManagedChannelBuilder;

/**
 * Represents a gRPC endpoint, consisting of a host and port.
 */
public record Endpoint(String host, int port) {

  /**
   * Creates a new gRPC channel connected to this endpoint.
   *
   * @return A new {@link ManagedChannel} instance.
   */
  public ManagedChannel createChannel() {
    // Build a ManagedChannel using the specified host and port.
    // usePlaintext() disables TLS for this connection. This is generally only suitable for
    // local testing or development environments. For production, enable TLS for secure
    // communication.
    return ManagedChannelBuilder
        .forAddress(host, port)
        .usePlaintext()
        .build();
  }
}
