package com.verlumen.tradestream.ingestion;

import com.google.auto.value.AutoValue;

@AutoValue
public abstract class Currency {
  static Currency create(String name) {
    return new AutoValue_Currency(name);
  }

  public abstract String name();
}
