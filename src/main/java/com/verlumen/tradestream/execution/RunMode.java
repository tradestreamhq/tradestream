package com.verlumen.tradestream.execution;

public enum RunMode {
  WET,
  DRY;

  static RunMode fromString(String name) {
    return RunMode.valueOf(name.toUpperCase());
  }
}
