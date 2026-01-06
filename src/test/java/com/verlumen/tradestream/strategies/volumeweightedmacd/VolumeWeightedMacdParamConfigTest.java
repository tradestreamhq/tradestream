package com.verlumen.tradestream.strategies.volumeweightedmacd;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotNull;

import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import org.junit.Test;

/** Tests for {@link VolumeWeightedMacdParamConfig}. */
public class VolumeWeightedMacdParamConfigTest {

  private final VolumeWeightedMacdParamConfig paramConfig = new VolumeWeightedMacdParamConfig();

  @Test
  public void testGetDefaultParameters() throws InvalidProtocolBufferException {
    Any defaultParams = paramConfig.getDefaultParameters();
    assertNotNull(defaultParams);

    var params = paramConfig.unpack(defaultParams);
    assertEquals(12, params.getShortPeriod());
    assertEquals(26, params.getLongPeriod());
    assertEquals(9, params.getSignalPeriod());
  }

  @Test
  public void testUnpack() throws InvalidProtocolBufferException {
    var originalParams =
        com.verlumen.tradestream.strategies.VolumeWeightedMacdParameters.newBuilder()
            .setShortPeriod(8)
            .setLongPeriod(21)
            .setSignalPeriod(5)
            .build();

    Any packedParams = Any.pack(originalParams);
    var unpackedParams = paramConfig.unpack(packedParams);

    assertEquals(8, unpackedParams.getShortPeriod());
    assertEquals(21, unpackedParams.getLongPeriod());
    assertEquals(5, unpackedParams.getSignalPeriod());
  }
}
