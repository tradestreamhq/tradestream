package com.verlumen.tradestream.discovery;

import com.google.common.collect.ImmutableList;
import com.verlumen.tradestream.backtesting.patternrecognition.PatternRecognitionParams;
import com.verlumen.tradestream.backtesting.trendfollowing.TrendFollowingParams;

final class ParamConfigs {
  static final ImmutableList<ParamConfig> ALL_CONFIGS =
      ImmutableList.<ParamConfig>builder()
          .addAll(PatternRecognitionParams.allConfigs)
          .addAll(TrendFollowingParams.allConfigs)
          .build();

  // Prevent instantiation
  private ParamConfigs() {}
}
