package com.verlumen.tradestream.execution;

import com.google.auto.value.AutoValue;
import com.google.inject.AbstractModule;

@AutoValue
public abstract class ExecutionModule extends AbstractModule {
  public static ExecutionModule create() {
    return new ExecutionModule();
  }
  
  @Override
  protected void configure() {}
}
