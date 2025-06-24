package com.verlumen.tradestream.strategies.momentumpinball;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotNull;

import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.StrategyType;
import org.junit.Test;

/** Tests for {@link MomentumPinballParamConfig}. */
public class MomentumPinballParamConfigTest {

  private final MomentumPinballParamConfig paramConfig = new MomentumPinballParamConfig();

  @Test
  public void testGetStrategyType() {
    assertEquals(StrategyType.MOMENTUM_PINBALL, paramConfig.getStrategyType());
  }

  @Test
  public void testGetDefaultParameters() throws InvalidProtocolBufferException {
    Any defaultParams = paramConfig.getDefaultParameters();
    assertNotNull(defaultParams);

    var params = paramConfig.unpack(defaultParams);
    assertEquals(10, params.getShortPeriod());
    assertEquals(20, params.getLongPeriod());
  }

  @Test
  public void testUnpack() throws InvalidProtocolBufferException {
    var originalParams =
        com.verlumen.tradestream.strategies.MomentumPinballParameters.newBuilder()
            .setShortPeriod(15)
            .setLongPeriod(30)
            .build();

    Any packedParams = Any.pack(originalParams);
    var unpackedParams = paramConfig.unpack(packedParams);

    assertEquals(15, unpackedParams.getShortPeriod());
    assertEquals(30, unpackedParams.getLongPeriod());
  }
}
