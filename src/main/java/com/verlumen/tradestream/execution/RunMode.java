package com.verlumen.tradestream.execution;

public enum RunMode {
  WET,
  DRY;

  public static RunMode fromString(String name) {
    return RunMode.valueOf(name.toUpperCase());
  }
}
