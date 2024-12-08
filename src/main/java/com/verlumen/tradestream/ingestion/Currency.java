package com.verlumen.tradestream.ingestion;

import com.google.auto.value.AutoValue;

@AutoValue
  abstract static class Currency {
    private static Currency create(String name) {
      return new AutoValue_Currency(name);
    }

    abstract String name();
  }
