package com.verlumen.tradestream.instruments;

import com.google.auto.value.AutoValue;

@AutoValue
public abstract static class Currency {
  private static Currency create(String name) {
    return new AutoValue_Currency(name);
  }

  abstract String name();
}
