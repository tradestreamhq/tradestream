package com.verlumen.tradestream.pipeline;

import com.google.inject.AbstractModule;

class PipelineModule extends AbstractModule {
  static PipelineModule create() {
    return new PipelineModule();
  }

  @Override
  protected void configure() {}
}
