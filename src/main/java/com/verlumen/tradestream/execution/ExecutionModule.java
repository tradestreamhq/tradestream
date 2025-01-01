package com.verlumen.tradestream.execution;

import com.google.auto.value.AutoValue;
import com.google.inject.AbstractModule;

@AutoValue
abstract class ExecutionModule extends AbstractModule {
  static ExecutionModule create(String runModeName) {
    RunMode runMode = RunMode.fromString(runModeName);
    return new AutoValue_ExecutionModule(runMode);
  }

  abstract RunMode runMode();
  
  @Override
  protected void configure() {
    bind(RunMode.class).toInstance(runMode());
  }
}
