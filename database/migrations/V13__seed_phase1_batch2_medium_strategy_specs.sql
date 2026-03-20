-- V13__seed_phase1_batch2_medium_strategy_specs.sql
-- Phase 1 Batch 2: Seed 15 medium-complexity strategy specs into the strategy_specs table.
-- These strategies use multiple indicators with compound entry/exit conditions.
-- References: Issue #1564 (migrate hardcoded strategies to config)

-- 16. ADX_DMI
INSERT INTO strategy_specs (name, version, description, complexity, indicators, entry_conditions, exit_conditions, parameters, source, tags)
VALUES (
  'ADX_DMI', 1,
  'ADX with Directional Movement Index - trades strong trends when +DI crosses -DI with ADX filter',
  'MEDIUM',
  '[{"id":"adx","type":"ADX","params":{"period":"${adxPeriod}"}},{"id":"plusDI","type":"PLUS_DI","params":{"period":"${diPeriod}"}},{"id":"minusDI","type":"MINUS_DI","params":{"period":"${diPeriod}"}}]'::jsonb,
  '[{"type":"OVER_CONSTANT","indicator":"adx","params":{"threshold":25}},{"type":"CROSSED_UP","indicator":"plusDI","params":{"crosses":"minusDI"}}]'::jsonb,
  '[{"type":"CROSSED_DOWN","indicator":"plusDI","params":{"crosses":"minusDI"}}]'::jsonb,
  '[{"name":"adxPeriod","type":"INTEGER","min":10,"max":30,"defaultValue":14},{"name":"diPeriod","type":"INTEGER","min":10,"max":30,"defaultValue":14}]'::jsonb,
  'MIGRATED',
  ARRAY['adx', 'dmi', 'trend-following', 'compound-entry', 'phase1-batch2']
) ON CONFLICT (name) DO NOTHING;

-- 17. ADX_STOCHASTIC
INSERT INTO strategy_specs (name, version, description, complexity, indicators, entry_conditions, exit_conditions, parameters, source, tags)
VALUES (
  'ADX_STOCHASTIC', 1,
  'ADX trend filter with Stochastic Oscillator - enters on strong trends when oversold',
  'MEDIUM',
  '[{"id":"adx","type":"ADX","params":{"period":"${adxPeriod}"}},{"id":"stochasticK","type":"STOCHASTIC_K","params":{"period":"${stochasticKPeriod}"}}]'::jsonb,
  '[{"type":"OVER_CONSTANT","indicator":"adx","params":{"threshold":20}},{"type":"UNDER_CONSTANT","indicator":"stochasticK","params":{"threshold":"${oversoldThreshold}"}}]'::jsonb,
  '[{"type":"UNDER_CONSTANT","indicator":"adx","params":{"threshold":20}},{"type":"OVER_CONSTANT","indicator":"stochasticK","params":{"threshold":"${overboughtThreshold}"}}]'::jsonb,
  '[{"name":"adxPeriod","type":"INTEGER","min":10,"max":30,"defaultValue":14},{"name":"stochasticKPeriod","type":"INTEGER","min":5,"max":21,"defaultValue":14},{"name":"overboughtThreshold","type":"INTEGER","min":70,"max":90,"defaultValue":80},{"name":"oversoldThreshold","type":"INTEGER","min":10,"max":30,"defaultValue":20}]'::jsonb,
  'MIGRATED',
  ARRAY['adx', 'stochastic', 'trend-following', 'oscillator', 'compound-entry', 'phase1-batch2']
) ON CONFLICT (name) DO NOTHING;

-- 18. AROON_MFI
INSERT INTO strategy_specs (name, version, description, complexity, indicators, entry_conditions, exit_conditions, parameters, source, tags)
VALUES (
  'AROON_MFI', 1,
  'Aroon with Money Flow Index - enters on Aroon Up crossing Down when MFI oversold',
  'MEDIUM',
  '[{"id":"aroonUp","type":"AROON_UP","params":{"period":"${aroonPeriod}"}},{"id":"aroonDown","type":"AROON_DOWN","params":{"period":"${aroonPeriod}"}},{"id":"mfi","type":"MFI","params":{"period":"${mfiPeriod}"}}]'::jsonb,
  '[{"type":"CROSSED_UP","indicator":"aroonUp","params":{"crosses":"aroonDown"}},{"type":"UNDER_CONSTANT","indicator":"mfi","params":{"threshold":"${oversoldThreshold}"}}]'::jsonb,
  '[{"type":"OVER","indicator":"aroonUp","params":{"other":"aroonDown"}},{"type":"OVER_CONSTANT","indicator":"mfi","params":{"threshold":"${overboughtThreshold}"}}]'::jsonb,
  '[{"name":"aroonPeriod","type":"INTEGER","min":15,"max":35,"defaultValue":25},{"name":"mfiPeriod","type":"INTEGER","min":7,"max":21,"defaultValue":14},{"name":"overboughtThreshold","type":"INTEGER","min":70,"max":90,"defaultValue":80},{"name":"oversoldThreshold","type":"INTEGER","min":10,"max":30,"defaultValue":20}]'::jsonb,
  'MIGRATED',
  ARRAY['aroon', 'mfi', 'trend-following', 'volume', 'compound-entry', 'phase1-batch2']
) ON CONFLICT (name) DO NOTHING;

-- 19. ATR_CCI
INSERT INTO strategy_specs (name, version, description, complexity, indicators, entry_conditions, exit_conditions, parameters, source, tags)
VALUES (
  'ATR_CCI', 1,
  'ATR volatility filter with CCI momentum - enters when CCI oversold and volatility rising',
  'MEDIUM',
  '[{"id":"atr","type":"ATR","params":{"period":"${atrPeriod}"}},{"id":"cci","type":"CCI","params":{"period":"${cciPeriod}"}},{"id":"previousAtr","type":"PREVIOUS","input":"atr","params":{"n":1}}]'::jsonb,
  '[{"type":"OVER_CONSTANT","indicator":"cci","params":{"threshold":-100}},{"type":"OVER","indicator":"atr","params":{"other":"previousAtr"}}]'::jsonb,
  '[{"type":"UNDER_CONSTANT","indicator":"cci","params":{"threshold":100}},{"type":"UNDER","indicator":"atr","params":{"other":"previousAtr"}}]'::jsonb,
  '[{"name":"atrPeriod","type":"INTEGER","min":7,"max":21,"defaultValue":14},{"name":"cciPeriod","type":"INTEGER","min":14,"max":28,"defaultValue":20}]'::jsonb,
  'MIGRATED',
  ARRAY['atr', 'cci', 'volatility', 'momentum', 'compound-entry', 'phase1-batch2']
) ON CONFLICT (name) DO NOTHING;

-- 20. BBAND_WILLIAMS_R
INSERT INTO strategy_specs (name, version, description, complexity, indicators, entry_conditions, exit_conditions, parameters, source, tags)
VALUES (
  'BBAND_WILLIAMS_R', 1,
  'Bollinger Bands with Williams %R - enters at lower band when Williams R oversold',
  'MEDIUM',
  '[{"id":"closePrice","type":"CLOSE"},{"id":"bbUpper","type":"BOLLINGER_UPPER","params":{"period":"${bbandsPeriod}","k":"${stdDevMultiplier}"}},{"id":"bbLower","type":"BOLLINGER_LOWER","params":{"period":"${bbandsPeriod}","k":"${stdDevMultiplier}"}},{"id":"williamsR","type":"WILLIAMS_R","params":{"period":"${wrPeriod}"}}]'::jsonb,
  '[{"type":"UNDER_INDICATOR","indicator":"closePrice","params":{"other":"bbLower"}},{"type":"UNDER_CONSTANT","indicator":"williamsR","params":{"threshold":-80}}]'::jsonb,
  '[{"type":"OVER_INDICATOR","indicator":"closePrice","params":{"other":"bbUpper"}},{"type":"OVER_CONSTANT","indicator":"williamsR","params":{"threshold":-20}}]'::jsonb,
  '[{"name":"bbandsPeriod","type":"INTEGER","min":10,"max":30,"defaultValue":20},{"name":"wrPeriod","type":"INTEGER","min":7,"max":21,"defaultValue":14},{"name":"stdDevMultiplier","type":"DOUBLE","min":1.5,"max":3.0,"defaultValue":2.0}]'::jsonb,
  'MIGRATED',
  ARRAY['bollinger', 'williams-r', 'mean-reversion', 'compound-entry', 'phase1-batch2']
) ON CONFLICT (name) DO NOTHING;

-- 21. CMO_MFI
INSERT INTO strategy_specs (name, version, description, complexity, indicators, entry_conditions, exit_conditions, parameters, source, tags)
VALUES (
  'CMO_MFI', 1,
  'Chande Momentum Oscillator with Money Flow Index - momentum and volume confirmation',
  'MEDIUM',
  '[{"id":"cmo","type":"CMO","params":{"period":"${cmoPeriod}"}},{"id":"mfi","type":"MFI","params":{"period":"${mfiPeriod}"}}]'::jsonb,
  '[{"type":"CROSSED_UP","indicator":"cmo","params":{"value":0}},{"type":"UNDER_CONSTANT","indicator":"mfi","params":{"threshold":20}}]'::jsonb,
  '[{"type":"CROSSED_DOWN","indicator":"cmo","params":{"value":0}},{"type":"OVER_CONSTANT","indicator":"mfi","params":{"threshold":80}}]'::jsonb,
  '[{"name":"cmoPeriod","type":"INTEGER","min":7,"max":21,"defaultValue":14},{"name":"mfiPeriod","type":"INTEGER","min":7,"max":21,"defaultValue":14}]'::jsonb,
  'MIGRATED',
  ARRAY['cmo', 'mfi', 'momentum', 'volume', 'compound-entry', 'phase1-batch2']
) ON CONFLICT (name) DO NOTHING;

-- 22. SMA_RSI
INSERT INTO strategy_specs (name, version, description, complexity, indicators, entry_conditions, exit_conditions, parameters, source, tags)
VALUES (
  'SMA_RSI', 1,
  'SMA trend filter combined with RSI overbought/oversold signals',
  'MEDIUM',
  '[{"id":"close","type":"CLOSE"},{"id":"sma","type":"SMA","input":"close","params":{"period":"${movingAveragePeriod}"}},{"id":"rsi","type":"RSI","input":"close","params":{"period":"${rsiPeriod}"}}]'::jsonb,
  '[{"type":"OVER","indicator":"close","params":{"other":"sma"}},{"type":"UNDER","indicator":"rsi","params":{"value":"${oversoldThreshold}"}}]'::jsonb,
  '[{"type":"OVER","indicator":"rsi","params":{"value":"${overboughtThreshold}"}}]'::jsonb,
  '[{"name":"movingAveragePeriod","type":"INTEGER","min":10,"max":50,"defaultValue":20},{"name":"rsiPeriod","type":"INTEGER","min":7,"max":21,"defaultValue":14},{"name":"overboughtThreshold","type":"DOUBLE","min":70.0,"max":85.0,"defaultValue":70.0},{"name":"oversoldThreshold","type":"DOUBLE","min":15.0,"max":30.0,"defaultValue":30.0}]'::jsonb,
  'MIGRATED',
  ARRAY['sma', 'rsi', 'trend-following', 'oscillator', 'compound-entry', 'phase1-batch2']
) ON CONFLICT (name) DO NOTHING;

-- 23. STOCHASTIC_EMA
INSERT INTO strategy_specs (name, version, description, complexity, indicators, entry_conditions, exit_conditions, parameters, source, tags)
VALUES (
  'STOCHASTIC_EMA', 1,
  'Stochastic oscillator with EMA trend filter for momentum trading',
  'MEDIUM',
  '[{"id":"close","type":"CLOSE"},{"id":"ema","type":"EMA","input":"close","params":{"period":"${emaPeriod}"}},{"id":"stochK","type":"STOCHASTIC_K","params":{"period":"${stochasticKPeriod}"}}]'::jsonb,
  '[{"type":"OVER","indicator":"close","params":{"other":"ema"}},{"type":"UNDER","indicator":"stochK","params":{"value":"${oversoldThreshold}"}}]'::jsonb,
  '[{"type":"OVER","indicator":"stochK","params":{"value":"${overboughtThreshold}"}}]'::jsonb,
  '[{"name":"emaPeriod","type":"INTEGER","min":10,"max":30,"defaultValue":20},{"name":"stochasticKPeriod","type":"INTEGER","min":10,"max":20,"defaultValue":14},{"name":"stochasticDPeriod","type":"INTEGER","min":3,"max":5,"defaultValue":3},{"name":"overboughtThreshold","type":"INTEGER","min":75,"max":90,"defaultValue":80},{"name":"oversoldThreshold","type":"INTEGER","min":10,"max":25,"defaultValue":20}]'::jsonb,
  'MIGRATED',
  ARRAY['stochastic', 'ema', 'momentum', 'trend-following', 'compound-entry', 'phase1-batch2']
) ON CONFLICT (name) DO NOTHING;

-- 24. STOCHASTIC_RSI
INSERT INTO strategy_specs (name, version, description, complexity, indicators, entry_conditions, exit_conditions, parameters, source, tags)
VALUES (
  'STOCHASTIC_RSI', 1,
  'Stochastic RSI combining RSI and Stochastic for momentum signals',
  'MEDIUM',
  '[{"id":"rsi","type":"RSI","params":{"period":"${rsiPeriod}"}},{"id":"stochasticK","type":"STOCHASTIC_K","params":{"period":"${stochasticKPeriod}"}}]'::jsonb,
  '[{"type":"OVER_CONSTANT","indicator":"stochasticK","params":{"threshold":"${oversoldThreshold}"}}]'::jsonb,
  '[{"type":"UNDER_CONSTANT","indicator":"stochasticK","params":{"threshold":"${overboughtThreshold}"}}]'::jsonb,
  '[{"name":"rsiPeriod","type":"INTEGER","min":7,"max":21,"defaultValue":14},{"name":"stochasticKPeriod","type":"INTEGER","min":7,"max":21,"defaultValue":14},{"name":"stochasticDPeriod","type":"INTEGER","min":2,"max":5,"defaultValue":3},{"name":"overboughtThreshold","type":"INTEGER","min":70,"max":90,"defaultValue":80},{"name":"oversoldThreshold","type":"INTEGER","min":10,"max":30,"defaultValue":20}]'::jsonb,
  'MIGRATED',
  ARRAY['stochastic', 'rsi', 'oscillator', 'momentum', 'phase1-batch2']
) ON CONFLICT (name) DO NOTHING;

-- 25. SAR_MFI
INSERT INTO strategy_specs (name, version, description, complexity, indicators, entry_conditions, exit_conditions, parameters, source, tags)
VALUES (
  'SAR_MFI', 1,
  'Parabolic SAR combined with Money Flow Index for trend confirmation with volume',
  'MEDIUM',
  '[{"id":"close","type":"CLOSE"},{"id":"sar","type":"PARABOLIC_SAR"},{"id":"mfi","type":"MFI","params":{"period":"${mfiPeriod}"}}]'::jsonb,
  '[{"type":"CROSSED_UP","indicator":"close","params":{"crosses":"sar"}},{"type":"UNDER","indicator":"mfi","params":{"value":30}}]'::jsonb,
  '[{"type":"CROSSED_DOWN","indicator":"close","params":{"crosses":"sar"}},{"type":"OVER","indicator":"mfi","params":{"value":70}}]'::jsonb,
  '[{"name":"accelerationFactorStart","type":"DOUBLE","min":0.01,"max":0.03,"defaultValue":0.02},{"name":"accelerationFactorIncrement","type":"DOUBLE","min":0.01,"max":0.03,"defaultValue":0.02},{"name":"accelerationFactorMax","type":"DOUBLE","min":0.15,"max":0.25,"defaultValue":0.20},{"name":"mfiPeriod","type":"INTEGER","min":10,"max":20,"defaultValue":14}]'::jsonb,
  'MIGRATED',
  ARRAY['parabolic-sar', 'mfi', 'trend-following', 'volume', 'compound-entry', 'phase1-batch2']
) ON CONFLICT (name) DO NOTHING;

-- 26. MOMENTUM_PINBALL
INSERT INTO strategy_specs (name, version, description, complexity, indicators, entry_conditions, exit_conditions, parameters, source, tags)
VALUES (
  'MOMENTUM_PINBALL', 1,
  'Combines short and long term momentum - enters when long momentum positive and short crosses zero',
  'MEDIUM',
  '[{"id":"shortMomentum","type":"MOMENTUM","input":"close","params":{"period":"${shortPeriod}"}},{"id":"longMomentum","type":"MOMENTUM","input":"close","params":{"period":"${longPeriod}"}}]'::jsonb,
  '[{"type":"OVER_CONSTANT","indicator":"longMomentum","params":{"threshold":0}},{"type":"CROSSED_UP","indicator":"shortMomentum","params":{"value":0}}]'::jsonb,
  '[{"type":"UNDER_CONSTANT","indicator":"longMomentum","params":{"threshold":0}},{"type":"CROSSED_DOWN","indicator":"shortMomentum","params":{"value":0}}]'::jsonb,
  '[{"name":"shortPeriod","type":"INTEGER","min":2,"max":30,"defaultValue":10},{"name":"longPeriod","type":"INTEGER","min":5,"max":60,"defaultValue":20}]'::jsonb,
  'MIGRATED',
  ARRAY['momentum', 'dual-timeframe', 'trend-following', 'compound-entry', 'phase1-batch2']
) ON CONFLICT (name) DO NOTHING;

-- 27. DONCHIAN_BREAKOUT
INSERT INTO strategy_specs (name, version, description, complexity, indicators, entry_conditions, exit_conditions, parameters, source, tags)
VALUES (
  'DONCHIAN_BREAKOUT', 1,
  'Donchian Channel breakout - enters when price breaks above highest high, exits at lowest low',
  'MEDIUM',
  '[{"id":"closePrice","type":"CLOSE"},{"id":"upperChannel","type":"DONCHIAN_UPPER","params":{"period":"${donchianPeriod}"}},{"id":"lowerChannel","type":"DONCHIAN_LOWER","params":{"period":"${donchianPeriod}"}}]'::jsonb,
  '[{"type":"OVER_INDICATOR","indicator":"closePrice","params":{"other":"upperChannel"}}]'::jsonb,
  '[{"type":"UNDER_INDICATOR","indicator":"closePrice","params":{"other":"lowerChannel"}}]'::jsonb,
  '[{"name":"donchianPeriod","type":"INTEGER","min":10,"max":50,"defaultValue":20}]'::jsonb,
  'MIGRATED',
  ARRAY['donchian', 'breakout', 'channel', 'trend-following', 'phase1-batch2']
) ON CONFLICT (name) DO NOTHING;

-- 28. VWAP_MEAN_REVERSION
INSERT INTO strategy_specs (name, version, description, complexity, indicators, entry_conditions, exit_conditions, parameters, source, tags)
VALUES (
  'VWAP_MEAN_REVERSION', 1,
  'VWAP mean reversion with Bollinger Bands - buys below VWAP at lower band, sells above at upper band',
  'MEDIUM',
  '[{"id":"close","type":"CLOSE"},{"id":"vwap","type":"VWAP","params":{"period":"${vwapPeriod}"}},{"id":"upperBand","type":"BOLLINGER_UPPER","input":"close","params":{"period":"${movingAveragePeriod}","multiplier":"${deviationMultiplier}"}},{"id":"lowerBand","type":"BOLLINGER_LOWER","input":"close","params":{"period":"${movingAveragePeriod}","multiplier":"${deviationMultiplier}"}}]'::jsonb,
  '[{"type":"UNDER","indicator":"close","params":{"other":"vwap"}},{"type":"CROSSED_UP","indicator":"close","params":{"crosses":"lowerBand"}}]'::jsonb,
  '[{"type":"OVER","indicator":"close","params":{"other":"vwap"}},{"type":"CROSSED_DOWN","indicator":"close","params":{"crosses":"upperBand"}}]'::jsonb,
  '[{"name":"vwapPeriod","type":"INTEGER","min":10,"max":30,"defaultValue":20},{"name":"movingAveragePeriod","type":"INTEGER","min":15,"max":30,"defaultValue":20},{"name":"deviationMultiplier","type":"DOUBLE","min":1.5,"max":3.0,"defaultValue":2.0}]'::jsonb,
  'MIGRATED',
  ARRAY['vwap', 'bollinger', 'mean-reversion', 'compound-entry', 'phase1-batch2']
) ON CONFLICT (name) DO NOTHING;

-- 29. VOLUME_BREAKOUT
INSERT INTO strategy_specs (name, version, description, complexity, indicators, entry_conditions, exit_conditions, parameters, source, tags)
VALUES (
  'VOLUME_BREAKOUT', 1,
  'Volume breakout strategy detecting high volume moves with price SMA confirmation',
  'MEDIUM',
  '[{"id":"close","type":"CLOSE"},{"id":"volume","type":"VOLUME"},{"id":"volumeSma","type":"SMA","input":"volume","params":{"period":20}},{"id":"priceSma","type":"SMA","input":"close","params":{"period":20}}]'::jsonb,
  '[{"type":"CROSSED_UP","indicator":"close","params":{"crosses":"priceSma"}},{"type":"IS_RISING","indicator":"volume","params":{"barCount":2}}]'::jsonb,
  '[{"type":"CROSSED_DOWN","indicator":"close","params":{"crosses":"priceSma"}}]'::jsonb,
  '[{"name":"volumeMultiplier","type":"DOUBLE","min":1.5,"max":3.0,"defaultValue":2.0}]'::jsonb,
  'MIGRATED',
  ARRAY['volume', 'breakout', 'price-action', 'compound-entry', 'phase1-batch2']
) ON CONFLICT (name) DO NOTHING;

-- 30. KST_OSCILLATOR
INSERT INTO strategy_specs (name, version, description, complexity, indicators, entry_conditions, exit_conditions, parameters, source, tags)
VALUES (
  'KST_OSCILLATOR', 1,
  'Know Sure Thing oscillator using weighted ROC indicators with signal line crossover',
  'MEDIUM',
  '[{"id":"close","type":"CLOSE"},{"id":"roc1","type":"ROC","input":"close","params":{"period":"${rma1Period}"}},{"id":"roc2","type":"ROC","input":"close","params":{"period":"${rma2Period}"}},{"id":"roc3","type":"ROC","input":"close","params":{"period":"${rma3Period}"}},{"id":"roc4","type":"ROC","input":"close","params":{"period":"${rma4Period}"}},{"id":"kstSignal","type":"SMA","input":"roc1","params":{"period":"${signalPeriod}"}}]'::jsonb,
  '[{"type":"CROSSED_UP","indicator":"roc1","params":{"crosses":"kstSignal"}}]'::jsonb,
  '[{"type":"CROSSED_DOWN","indicator":"roc1","params":{"crosses":"kstSignal"}}]'::jsonb,
  '[{"name":"rma1Period","type":"INTEGER","min":8,"max":12,"defaultValue":10},{"name":"rma2Period","type":"INTEGER","min":13,"max":17,"defaultValue":15},{"name":"rma3Period","type":"INTEGER","min":18,"max":22,"defaultValue":20},{"name":"rma4Period","type":"INTEGER","min":28,"max":32,"defaultValue":30},{"name":"signalPeriod","type":"INTEGER","min":7,"max":11,"defaultValue":9}]'::jsonb,
  'MIGRATED',
  ARRAY['kst', 'roc', 'momentum', 'oscillator', 'multi-indicator', 'phase1-batch2']
) ON CONFLICT (name) DO NOTHING;
