package com.verlumen.tradestream.ta4j;

import com.google.inject.AbstractModule;

public class Ta4jModule extends AbstractModule {
  public static Ta4jModule create() {
    return new Ta4jModule();
  }

  @Override
  protected void configure() {
    bind(BarSeriesFactory.class).toInstance(BarSeriesBuilder::createBarSeries);
  }

  private Ta4jModule() {}
}
