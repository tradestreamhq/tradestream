package com.verlumen.tradestream.execution;

public enum RunMode {
  public static RunMode fromString(String name) {
    return RunMode.valueOf(name.toUpperCase());
  }
  
  WET,
  DRY;
}
