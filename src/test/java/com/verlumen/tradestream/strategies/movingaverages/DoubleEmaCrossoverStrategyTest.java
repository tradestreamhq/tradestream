package com.verlumen.tradestream.strategies.movingaverages;

import static com.google.common.truth.Truth.assertThat;

import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.StrategyType;
import com.verlumen.tradestream.strategies.DoubleEmaCrossoverParameters;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.ta4j.core.Strategy;

@RunWith(JUnit4.class)
public class DoubleEmaCrossoverStrategyTest {

  private DoubleEmaCrossoverStrategyFactory factory;

  @Before
  public void setUp() {
    factory = new DoubleEmaCrossoverStrategy();
  }

  @Test
  public void getStrategyType() {
    assertThat(factory.getStrategyType()).isEqualTo(StrategyType.DOUBLE_EMA_CROSSOVER);
  }

  @Test
  public void getParameterClass() {
    assertThat(factory.getParameterClass()).isEqualTo(DoubleEmaCrossoverParameters.class);
  }

  @Test
  public void createStrategy_withParams() throws InvalidProtocolBufferException {
    DoubleEmaCrossoverParameters params = DoubleEmaCrossoverParameters.newBuilder().setShortEmaPeriod(5).setLongEmaPeriod(20).build();
    Strategy strategy = factory.createStrategy(params);
    assertThat(strategy).isNotNull();
  }
}
