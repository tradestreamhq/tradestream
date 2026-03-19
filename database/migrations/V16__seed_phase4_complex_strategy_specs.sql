-- V16__seed_phase4_complex_strategy_specs.sql
-- Phase 4: Seed the remaining 30 complex strategy specs into the strategy_specs table.
-- These strategies use multi-indicator setups, state-based logic, volume profiles,
-- and advanced channel/volatility techniques.
-- References: Issue #1487 (Phase 4 sprint), Issue #1564 (migrate all 60 strategies)

-- 31. ATR_TRAILING_STOP
INSERT INTO strategy_specs (name, version, description, complexity, indicators, entry_conditions, exit_conditions, parameters, source, tags)
VALUES (
  'ATR_TRAILING_STOP', 1,
  'ATR-based trailing stop - enters on price momentum, exits on trailing stop loss',
  'COMPLEX',
  '[{"id":"closePrice","type":"CLOSE"},{"id":"previousClose","type":"PREVIOUS","input":"closePrice","params":{"n":1}},{"id":"atr","type":"ATR","params":{"period":"${atrPeriod}"}}]'::jsonb,
  '[{"type":"ABOVE","indicator":"closePrice","params":{"other":"previousClose"}}]'::jsonb,
  '[{"type":"TRAILING_STOP_LOSS","params":{"percentage":"${multiplier}"}}]'::jsonb,
  '[{"name":"atrPeriod","type":"INTEGER","min":5,"max":30,"defaultValue":14},{"name":"multiplier","type":"DOUBLE","min":1.0,"max":5.0,"defaultValue":3.0}]'::jsonb,
  'MIGRATED',
  ARRAY['atr', 'trailing-stop', 'volatility', 'risk-management', 'phase4']
) ON CONFLICT (name) DO NOTHING;

-- 32. CMF_ZERO_LINE
INSERT INTO strategy_specs (name, version, description, complexity, indicators, entry_conditions, exit_conditions, parameters, source, tags)
VALUES (
  'CMF_ZERO_LINE', 1,
  'Chaikin Money Flow zero-line crossover - enters when CMF crosses above zero',
  'COMPLEX',
  '[{"id":"cmf","type":"CMF","params":{"period":"${period}"}}]'::jsonb,
  '[{"type":"CROSSED_UP","indicator":"cmf","params":{"value":0}}]'::jsonb,
  '[{"type":"CROSSED_DOWN","indicator":"cmf","params":{"value":0}}]'::jsonb,
  '[{"name":"period","type":"INTEGER","min":10,"max":50,"defaultValue":20}]'::jsonb,
  'MIGRATED',
  ARRAY['cmf', 'zero-line', 'volume', 'phase4']
) ON CONFLICT (name) DO NOTHING;

-- 33. DOUBLE_TOP_BOTTOM
INSERT INTO strategy_specs (name, version, description, complexity, indicators, entry_conditions, exit_conditions, parameters, source, tags)
VALUES (
  'DOUBLE_TOP_BOTTOM', 1,
  'Double Top/Bottom pattern using EMA crossover for reversal detection',
  'COMPLEX',
  '[{"id":"closePrice","type":"CLOSE"},{"id":"ema","type":"EMA","params":{"period":"${period}"}}]'::jsonb,
  '[{"type":"CROSSED_UP","indicator":"closePrice","params":{"crosses":"ema"}}]'::jsonb,
  '[{"type":"CROSSED_DOWN","indicator":"closePrice","params":{"crosses":"ema"}}]'::jsonb,
  '[{"name":"period","type":"INTEGER","min":10,"max":50,"defaultValue":20}]'::jsonb,
  'MIGRATED',
  ARRAY['pattern', 'reversal', 'ema', 'price-action', 'phase4']
) ON CONFLICT (name) DO NOTHING;

-- 34. ELDER_RAY_MA
INSERT INTO strategy_specs (name, version, description, complexity, indicators, entry_conditions, exit_conditions, parameters, source, tags)
VALUES (
  'ELDER_RAY_MA', 1,
  'Elder Ray with EMA - enters when high crosses above EMA (bull power), exits when low crosses below',
  'COMPLEX',
  '[{"id":"highPrice","type":"HIGH"},{"id":"lowPrice","type":"LOW"},{"id":"ema","type":"EMA","params":{"period":"${emaPeriod}"}}]'::jsonb,
  '[{"type":"CROSSED_UP","indicator":"highPrice","params":{"crosses":"ema"}}]'::jsonb,
  '[{"type":"CROSSED_DOWN","indicator":"lowPrice","params":{"crosses":"ema"}}]'::jsonb,
  '[{"name":"emaPeriod","type":"INTEGER","min":10,"max":30,"defaultValue":20}]'::jsonb,
  'MIGRATED',
  ARRAY['elder-ray', 'ema', 'trend-following', 'bull-bear-power', 'phase4']
) ON CONFLICT (name) DO NOTHING;

-- 35. EMA_MACD
INSERT INTO strategy_specs (name, version, description, complexity, indicators, entry_conditions, exit_conditions, parameters, source, tags)
VALUES (
  'EMA_MACD', 1,
  'EMA-based MACD - enters when MACD crosses above signal line',
  'COMPLEX',
  '[{"id":"macd","type":"MACD","params":{"shortPeriod":"${shortEmaPeriod}","longPeriod":"${longEmaPeriod}"}},{"id":"signalLine","type":"EMA","input":"macd","params":{"period":"${signalPeriod}"}}]'::jsonb,
  '[{"type":"CROSSED_UP","indicator":"macd","params":{"crosses":"signalLine"}}]'::jsonb,
  '[{"type":"CROSSED_DOWN","indicator":"macd","params":{"crosses":"signalLine"}}]'::jsonb,
  '[{"name":"shortEmaPeriod","type":"INTEGER","min":8,"max":16,"defaultValue":12},{"name":"longEmaPeriod","type":"INTEGER","min":20,"max":32,"defaultValue":26},{"name":"signalPeriod","type":"INTEGER","min":6,"max":12,"defaultValue":9}]'::jsonb,
  'MIGRATED',
  ARRAY['ema', 'macd', 'momentum', 'crossover', 'phase4']
) ON CONFLICT (name) DO NOTHING;

-- 36. FIBONACCI_RETRACEMENTS
INSERT INTO strategy_specs (name, version, description, complexity, indicators, entry_conditions, exit_conditions, parameters, source, tags)
VALUES (
  'FIBONACCI_RETRACEMENTS', 1,
  'Fibonacci retracement levels for support/resistance trading using Donchian channels',
  'COMPLEX',
  '[{"id":"close","type":"CLOSE"},{"id":"high","type":"DONCHIAN_UPPER","params":{"period":"${period}"}},{"id":"low","type":"DONCHIAN_LOWER","params":{"period":"${period}"}},{"id":"middle","type":"DONCHIAN_MIDDLE","params":{"period":"${period}"}}]'::jsonb,
  '[{"type":"CROSSED_UP","indicator":"close","params":{"crosses":"low"}}]'::jsonb,
  '[{"type":"CROSSED_DOWN","indicator":"close","params":{"crosses":"high"}}]'::jsonb,
  '[{"name":"period","type":"INTEGER","min":20,"max":100,"defaultValue":50}]'::jsonb,
  'MIGRATED',
  ARRAY['fibonacci', 'support-resistance', 'channel', 'price-action', 'phase4']
) ON CONFLICT (name) DO NOTHING;

-- 37. FRAMA
INSERT INTO strategy_specs (name, version, description, complexity, indicators, entry_conditions, exit_conditions, parameters, source, tags)
VALUES (
  'FRAMA', 1,
  'Fractal Adaptive Moving Average - enters when price crosses above FRAMA, exits when crosses below',
  'COMPLEX',
  '[{"id":"close","type":"CLOSE"},{"id":"frama","type":"FRAMA","params":{"sc":"${sc}","fc":"${fc}","alpha":"${alpha}"}}]'::jsonb,
  '[{"type":"CROSSED_UP","indicator":"close","params":{"crosses":"frama"}}]'::jsonb,
  '[{"type":"CROSSED_DOWN","indicator":"close","params":{"crosses":"frama"}}]'::jsonb,
  '[{"name":"sc","type":"DOUBLE","min":0.1,"max":2.0,"defaultValue":0.5},{"name":"fc","type":"INTEGER","min":5,"max":50,"defaultValue":20},{"name":"alpha","type":"DOUBLE","min":0.1,"max":1.0,"defaultValue":0.5}]'::jsonb,
  'MIGRATED',
  ARRAY['frama', 'adaptive', 'fractal', 'trend-following', 'phase4']
) ON CONFLICT (name) DO NOTHING;

-- 38. GANN_SWING
INSERT INTO strategy_specs (name, version, description, complexity, indicators, entry_conditions, exit_conditions, parameters, source, tags)
VALUES (
  'GANN_SWING', 1,
  'Gann swing trading strategy using Donchian channels for swing high/low breakouts',
  'COMPLEX',
  '[{"id":"close","type":"CLOSE"},{"id":"swingHigh","type":"DONCHIAN_UPPER","params":{"period":"${gannPeriod}"}},{"id":"swingLow","type":"DONCHIAN_LOWER","params":{"period":"${gannPeriod}"}}]'::jsonb,
  '[{"type":"CROSSED_UP","indicator":"close","params":{"crosses":"swingHigh"}}]'::jsonb,
  '[{"type":"CROSSED_DOWN","indicator":"close","params":{"crosses":"swingLow"}}]'::jsonb,
  '[{"name":"gannPeriod","type":"INTEGER","min":5,"max":30,"defaultValue":10}]'::jsonb,
  'MIGRATED',
  ARRAY['gann', 'swing', 'breakout', 'channel', 'phase4']
) ON CONFLICT (name) DO NOTHING;

-- 39. HEIKEN_ASHI
INSERT INTO strategy_specs (name, version, description, complexity, indicators, entry_conditions, exit_conditions, parameters, source, tags)
VALUES (
  'HEIKEN_ASHI', 1,
  'Heiken Ashi candle strategy - enters when HA close crosses above HA open, exits on reversal',
  'COMPLEX',
  '[{"id":"heikenAshiClose","type":"HEIKEN_ASHI_CLOSE","params":{"period":"${period}"}},{"id":"heikenAshiOpen","type":"HEIKEN_ASHI_OPEN","params":{"period":"${period}"}}]'::jsonb,
  '[{"type":"CROSSED_UP","indicator":"heikenAshiClose","params":{"crosses":"heikenAshiOpen"}}]'::jsonb,
  '[{"type":"CROSSED_DOWN","indicator":"heikenAshiClose","params":{"crosses":"heikenAshiOpen"}}]'::jsonb,
  '[{"name":"period","type":"INTEGER","min":2,"max":30,"defaultValue":14}]'::jsonb,
  'MIGRATED',
  ARRAY['heiken-ashi', 'candle', 'trend-following', 'japanese', 'phase4']
) ON CONFLICT (name) DO NOTHING;

-- 40. ICHIMOKU_CLOUD
INSERT INTO strategy_specs (name, version, description, complexity, indicators, entry_conditions, exit_conditions, parameters, source, tags)
VALUES (
  'ICHIMOKU_CLOUD', 1,
  'Ichimoku Cloud using EMAs for Tenkan/Kijun crossovers with cloud confirmation',
  'COMPLEX',
  '[{"id":"close","type":"CLOSE"},{"id":"tenkanSen","type":"EMA","input":"close","params":{"period":"${tenkanSenPeriod}"}},{"id":"kijunSen","type":"EMA","input":"close","params":{"period":"${kijunSenPeriod}"}},{"id":"senkouSpanB","type":"EMA","input":"close","params":{"period":"${senkouSpanBPeriod}"}}]'::jsonb,
  '[{"type":"CROSSED_UP","indicator":"tenkanSen","params":{"crosses":"kijunSen"}},{"type":"OVER","indicator":"close","params":{"other":"senkouSpanB"}}]'::jsonb,
  '[{"type":"CROSSED_DOWN","indicator":"tenkanSen","params":{"crosses":"kijunSen"}}]'::jsonb,
  '[{"name":"tenkanSenPeriod","type":"INTEGER","min":7,"max":12,"defaultValue":9},{"name":"kijunSenPeriod","type":"INTEGER","min":20,"max":30,"defaultValue":26},{"name":"senkouSpanBPeriod","type":"INTEGER","min":45,"max":60,"defaultValue":52},{"name":"chikouSpanPeriod","type":"INTEGER","min":20,"max":30,"defaultValue":26}]'::jsonb,
  'MIGRATED',
  ARRAY['ichimoku', 'cloud', 'trend-following', 'multi-indicator', 'japanese', 'phase4']
) ON CONFLICT (name) DO NOTHING;

-- 41. KLINGER_VOLUME
INSERT INTO strategy_specs (name, version, description, complexity, indicators, entry_conditions, exit_conditions, parameters, source, tags)
VALUES (
  'KLINGER_VOLUME', 1,
  'Klinger Volume Oscillator with signal line - volume-based trend detection',
  'COMPLEX',
  '[{"id":"kvo","type":"KLINGER_VOLUME_OSCILLATOR","params":{"shortPeriod":"${shortPeriod}","longPeriod":"${longPeriod}"}},{"id":"signalLine","type":"EMA","input":"kvo","params":{"period":"${signalPeriod}"}}]'::jsonb,
  '[{"type":"CROSSED_UP","indicator":"kvo","params":{"crosses":"signalLine"}}]'::jsonb,
  '[{"type":"CROSSED_DOWN","indicator":"kvo","params":{"crosses":"signalLine"}}]'::jsonb,
  '[{"name":"shortPeriod","type":"INTEGER","min":5,"max":20,"defaultValue":10},{"name":"longPeriod","type":"INTEGER","min":20,"max":50,"defaultValue":35},{"name":"signalPeriod","type":"INTEGER","min":5,"max":15,"defaultValue":10}]'::jsonb,
  'MIGRATED',
  ARRAY['klinger', 'volume', 'oscillator', 'trend-following', 'phase4']
) ON CONFLICT (name) DO NOTHING;

-- 42. LINEAR_REGRESSION_CHANNELS
INSERT INTO strategy_specs (name, version, description, complexity, indicators, entry_conditions, exit_conditions, parameters, source, tags)
VALUES (
  'LINEAR_REGRESSION_CHANNELS', 1,
  'Linear Regression Channels - Bollinger Band proxy for channel breakout/reversion',
  'COMPLEX',
  '[{"id":"close","type":"CLOSE"},{"id":"upper","type":"BOLLINGER_UPPER","input":"close","params":{"period":"${period}","multiplier":"${multiplier}"}},{"id":"lower","type":"BOLLINGER_LOWER","input":"close","params":{"period":"${period}","multiplier":"${multiplier}"}}]'::jsonb,
  '[{"type":"CROSSED_UP","indicator":"close","params":{"crosses":"lower"}}]'::jsonb,
  '[{"type":"CROSSED_DOWN","indicator":"close","params":{"crosses":"upper"}}]'::jsonb,
  '[{"name":"period","type":"INTEGER","min":10,"max":50,"defaultValue":20},{"name":"multiplier","type":"DOUBLE","min":1.0,"max":3.0,"defaultValue":2.0}]'::jsonb,
  'MIGRATED',
  ARRAY['linear-regression', 'channel', 'mean-reversion', 'statistical', 'phase4']
) ON CONFLICT (name) DO NOTHING;

-- 43. MASS_INDEX
INSERT INTO strategy_specs (name, version, description, complexity, indicators, entry_conditions, exit_conditions, parameters, source, tags)
VALUES (
  'MASS_INDEX', 1,
  'Mass Index reversal bulge strategy - identifies trend reversals via range expansion',
  'COMPLEX',
  '[{"id":"massIndex","type":"MASS_INDEX","params":{"emaPeriod":"${emaPeriod}","sumPeriod":"${sumPeriod}"}}]'::jsonb,
  '[{"type":"CROSSED_DOWN_CONSTANT","indicator":"massIndex","params":{"threshold":26.5}}]'::jsonb,
  '[{"type":"CROSSED_UP_CONSTANT","indicator":"massIndex","params":{"threshold":27}},{"type":"CROSSED_DOWN_CONSTANT","indicator":"massIndex","params":{"threshold":25}}]'::jsonb,
  '[{"name":"emaPeriod","type":"INTEGER","min":5,"max":15,"defaultValue":9},{"name":"sumPeriod","type":"INTEGER","min":15,"max":35,"defaultValue":25}]'::jsonb,
  'MIGRATED',
  ARRAY['mass-index', 'reversal', 'volatility', 'range-expansion', 'phase4']
) ON CONFLICT (name) DO NOTHING;

-- 44. PARABOLIC_SAR
INSERT INTO strategy_specs (name, version, description, complexity, indicators, entry_conditions, exit_conditions, parameters, source, tags)
VALUES (
  'PARABOLIC_SAR', 1,
  'Parabolic SAR trend-following strategy for stop and reverse signals',
  'COMPLEX',
  '[{"id":"close","type":"CLOSE"},{"id":"sar","type":"PARABOLIC_SAR"}]'::jsonb,
  '[{"type":"CROSSED_UP","indicator":"close","params":{"crosses":"sar"}}]'::jsonb,
  '[{"type":"CROSSED_DOWN","indicator":"close","params":{"crosses":"sar"}}]'::jsonb,
  '[{"name":"accelerationFactorStart","type":"DOUBLE","min":0.01,"max":0.03,"defaultValue":0.02},{"name":"accelerationFactorIncrement","type":"DOUBLE","min":0.01,"max":0.03,"defaultValue":0.02},{"name":"accelerationFactorMax","type":"DOUBLE","min":0.15,"max":0.25,"defaultValue":0.20}]'::jsonb,
  'MIGRATED',
  ARRAY['parabolic-sar', 'trend-following', 'stop-reverse', 'phase4']
) ON CONFLICT (name) DO NOTHING;

-- 45. PIVOT
INSERT INTO strategy_specs (name, version, description, complexity, indicators, entry_conditions, exit_conditions, parameters, source, tags)
VALUES (
  'PIVOT', 1,
  'Pivot point strategy using Donchian channels for support/resistance breakout',
  'COMPLEX',
  '[{"id":"close","type":"CLOSE"},{"id":"typicalPrice","type":"TYPICAL_PRICE"},{"id":"pivotHigh","type":"DONCHIAN_UPPER","params":{"period":"${period}"}},{"id":"pivotLow","type":"DONCHIAN_LOWER","params":{"period":"${period}"}}]'::jsonb,
  '[{"type":"CROSSED_UP","indicator":"close","params":{"crosses":"pivotLow"}}]'::jsonb,
  '[{"type":"CROSSED_DOWN","indicator":"close","params":{"crosses":"pivotHigh"}}]'::jsonb,
  '[{"name":"period","type":"INTEGER","min":5,"max":20,"defaultValue":10}]'::jsonb,
  'MIGRATED',
  ARRAY['pivot', 'support-resistance', 'breakout', 'price-action', 'phase4']
) ON CONFLICT (name) DO NOTHING;

-- 46. PRICE_GAP
INSERT INTO strategy_specs (name, version, description, complexity, indicators, entry_conditions, exit_conditions, parameters, source, tags)
VALUES (
  'PRICE_GAP', 1,
  'Price gap strategy using EMA crossover for gap fill detection',
  'COMPLEX',
  '[{"id":"closePrice","type":"CLOSE"},{"id":"ema","type":"EMA","params":{"period":"${period}"}}]'::jsonb,
  '[{"type":"CROSSED_UP","indicator":"closePrice","params":{"crosses":"ema"}}]'::jsonb,
  '[{"type":"CROSSED_DOWN","indicator":"closePrice","params":{"crosses":"ema"}}]'::jsonb,
  '[{"name":"period","type":"INTEGER","min":5,"max":20,"defaultValue":10}]'::jsonb,
  'MIGRATED',
  ARRAY['price-gap', 'gap-fill', 'ema', 'price-action', 'phase4']
) ON CONFLICT (name) DO NOTHING;

-- 47. PRICE_OSCILLATOR_SIGNAL
INSERT INTO strategy_specs (name, version, description, complexity, indicators, entry_conditions, exit_conditions, parameters, source, tags)
VALUES (
  'PRICE_OSCILLATOR_SIGNAL', 1,
  'Price Oscillator with signal line crossover for momentum trading',
  'COMPLEX',
  '[{"id":"close","type":"CLOSE"},{"id":"priceOscillator","type":"MACD","input":"close","params":{"shortPeriod":"${fastPeriod}","longPeriod":"${slowPeriod}"}},{"id":"signalLine","type":"EMA","input":"priceOscillator","params":{"period":"${signalPeriod}"}}]'::jsonb,
  '[{"type":"CROSSED_UP","indicator":"priceOscillator","params":{"crosses":"signalLine"}}]'::jsonb,
  '[{"type":"CROSSED_DOWN","indicator":"priceOscillator","params":{"crosses":"signalLine"}}]'::jsonb,
  '[{"name":"fastPeriod","type":"INTEGER","min":5,"max":20,"defaultValue":10},{"name":"slowPeriod","type":"INTEGER","min":10,"max":50,"defaultValue":20},{"name":"signalPeriod","type":"INTEGER","min":5,"max":20,"defaultValue":9}]'::jsonb,
  'MIGRATED',
  ARRAY['price-oscillator', 'momentum', 'crossover', 'phase4']
) ON CONFLICT (name) DO NOTHING;

-- 48. RAINBOW_OSCILLATOR
INSERT INTO strategy_specs (name, version, description, complexity, indicators, entry_conditions, exit_conditions, parameters, source, tags)
VALUES (
  'RAINBOW_OSCILLATOR', 1,
  'Rainbow oscillator using stacked EMAs for trend confirmation',
  'COMPLEX',
  '[{"id":"close","type":"CLOSE"},{"id":"ema1","type":"EMA","input":"close","params":{"period":5}},{"id":"ema2","type":"EMA","input":"close","params":{"period":10}},{"id":"ema3","type":"EMA","input":"close","params":{"period":20}}]'::jsonb,
  '[{"type":"OVER","indicator":"ema1","params":{"other":"ema2"}},{"type":"OVER","indicator":"ema2","params":{"other":"ema3"}}]'::jsonb,
  '[{"type":"UNDER","indicator":"ema1","params":{"other":"ema2"}}]'::jsonb,
  '[]'::jsonb,
  'MIGRATED',
  ARRAY['rainbow', 'ema', 'multi-indicator', 'trend-following', 'phase4']
) ON CONFLICT (name) DO NOTHING;

-- 49. RANGE_BARS
INSERT INTO strategy_specs (name, version, description, complexity, indicators, entry_conditions, exit_conditions, parameters, source, tags)
VALUES (
  'RANGE_BARS', 1,
  'Range bars strategy using Bollinger Band breakouts for volatility-based entries',
  'COMPLEX',
  '[{"id":"close","type":"CLOSE"},{"id":"atr","type":"ATR","params":{"period":14}},{"id":"upperRange","type":"BOLLINGER_UPPER","input":"close","params":{"period":20,"multiplier":"${rangeSize}"}},{"id":"lowerRange","type":"BOLLINGER_LOWER","input":"close","params":{"period":20,"multiplier":"${rangeSize}"}}]'::jsonb,
  '[{"type":"CROSSED_UP","indicator":"close","params":{"crosses":"upperRange"}}]'::jsonb,
  '[{"type":"CROSSED_DOWN","indicator":"close","params":{"crosses":"lowerRange"}}]'::jsonb,
  '[{"name":"rangeSize","type":"DOUBLE","min":1.0,"max":3.0,"defaultValue":2.0}]'::jsonb,
  'MIGRATED',
  ARRAY['range-bars', 'bollinger', 'volatility', 'breakout', 'phase4']
) ON CONFLICT (name) DO NOTHING;

-- 50. REGRESSION_CHANNEL
INSERT INTO strategy_specs (name, version, description, complexity, indicators, entry_conditions, exit_conditions, parameters, source, tags)
VALUES (
  'REGRESSION_CHANNEL', 1,
  'Regression channel mean reversion strategy using Bollinger Bands as channel proxy',
  'COMPLEX',
  '[{"id":"close","type":"CLOSE"},{"id":"middle","type":"BOLLINGER_MIDDLE","input":"close","params":{"period":"${period}"}},{"id":"upper","type":"BOLLINGER_UPPER","input":"close","params":{"period":"${period}","multiplier":2.0}},{"id":"lower","type":"BOLLINGER_LOWER","input":"close","params":{"period":"${period}","multiplier":2.0}}]'::jsonb,
  '[{"type":"CROSSED_UP","indicator":"close","params":{"crosses":"lower"}}]'::jsonb,
  '[{"type":"CROSSED_DOWN","indicator":"close","params":{"crosses":"upper"}}]'::jsonb,
  '[{"name":"period","type":"INTEGER","min":15,"max":50,"defaultValue":20}]'::jsonb,
  'MIGRATED',
  ARRAY['regression', 'channel', 'bollinger', 'mean-reversion', 'phase4']
) ON CONFLICT (name) DO NOTHING;

-- 51. RENKO_CHART
INSERT INTO strategy_specs (name, version, description, complexity, indicators, entry_conditions, exit_conditions, parameters, source, tags)
VALUES (
  'RENKO_CHART', 1,
  'Renko chart style strategy using ATR volatility and EMA for trend following',
  'COMPLEX',
  '[{"id":"close","type":"CLOSE"},{"id":"atr","type":"ATR","params":{"period":14}},{"id":"ema","type":"EMA","input":"close","params":{"period":20}}]'::jsonb,
  '[{"type":"CROSSED_UP","indicator":"close","params":{"crosses":"ema"}},{"type":"IS_RISING","indicator":"close","params":{"barCount":2}}]'::jsonb,
  '[{"type":"CROSSED_DOWN","indicator":"close","params":{"crosses":"ema"}}]'::jsonb,
  '[{"name":"brickSize","type":"DOUBLE","min":0.5,"max":3.0,"defaultValue":1.0}]'::jsonb,
  'MIGRATED',
  ARRAY['renko', 'atr', 'trend-following', 'price-action', 'phase4']
) ON CONFLICT (name) DO NOTHING;

-- 52. RVI
INSERT INTO strategy_specs (name, version, description, complexity, indicators, entry_conditions, exit_conditions, parameters, source, tags)
VALUES (
  'RVI', 1,
  'Relative Vigor Index using RSI as vigor proxy with SMA signal line crossover',
  'COMPLEX',
  '[{"id":"close","type":"CLOSE"},{"id":"rvi","type":"RSI","input":"close","params":{"period":"${period}"}},{"id":"rviSignal","type":"SMA","input":"rvi","params":{"period":4}}]'::jsonb,
  '[{"type":"CROSSED_UP","indicator":"rvi","params":{"crosses":"rviSignal"}}]'::jsonb,
  '[{"type":"CROSSED_DOWN","indicator":"rvi","params":{"crosses":"rviSignal"}}]'::jsonb,
  '[{"name":"period","type":"INTEGER","min":7,"max":21,"defaultValue":10}]'::jsonb,
  'MIGRATED',
  ARRAY['rvi', 'rsi', 'oscillator', 'crossover', 'phase4']
) ON CONFLICT (name) DO NOTHING;

-- 53. TICK_VOLUME_ANALYSIS
INSERT INTO strategy_specs (name, version, description, complexity, indicators, entry_conditions, exit_conditions, parameters, source, tags)
VALUES (
  'TICK_VOLUME_ANALYSIS', 1,
  'Tick volume analysis using volume EMA confirmation with price EMA crossover',
  'COMPLEX',
  '[{"id":"volume","type":"VOLUME"},{"id":"volumeEma","type":"EMA","input":"volume","params":{"period":"${tickPeriod}"}},{"id":"close","type":"CLOSE"},{"id":"priceEma","type":"EMA","input":"close","params":{"period":"${tickPeriod}"}}]'::jsonb,
  '[{"type":"OVER","indicator":"volume","params":{"other":"volumeEma"}},{"type":"CROSSED_UP","indicator":"close","params":{"crosses":"priceEma"}}]'::jsonb,
  '[{"type":"CROSSED_DOWN","indicator":"close","params":{"crosses":"priceEma"}}]'::jsonb,
  '[{"name":"tickPeriod","type":"INTEGER","min":10,"max":30,"defaultValue":20}]'::jsonb,
  'MIGRATED',
  ARRAY['tick-volume', 'volume', 'ema', 'compound-entry', 'phase4']
) ON CONFLICT (name) DO NOTHING;

-- 54. TRIX_SIGNAL_LINE
INSERT INTO strategy_specs (name, version, description, complexity, indicators, entry_conditions, exit_conditions, parameters, source, tags)
VALUES (
  'TRIX_SIGNAL_LINE', 1,
  'TRIX with SMA signal line crossover for smoothed momentum trading',
  'COMPLEX',
  '[{"id":"trix","type":"TRIX","params":{"period":"${trixPeriod}"}},{"id":"signalLine","type":"SMA","input":"trix","params":{"period":"${signalPeriod}"}}]'::jsonb,
  '[{"type":"CROSSED_UP","indicator":"trix","params":{"crosses":"signalLine"}}]'::jsonb,
  '[{"type":"CROSSED_DOWN","indicator":"trix","params":{"crosses":"signalLine"}}]'::jsonb,
  '[{"name":"trixPeriod","type":"INTEGER","min":5,"max":50,"defaultValue":15},{"name":"signalPeriod","type":"INTEGER","min":3,"max":20,"defaultValue":9}]'::jsonb,
  'MIGRATED',
  ARRAY['trix', 'momentum', 'oscillator', 'crossover', 'phase4']
) ON CONFLICT (name) DO NOTHING;

-- 55. VARIABLE_PERIOD_EMA
INSERT INTO strategy_specs (name, version, description, complexity, indicators, entry_conditions, exit_conditions, parameters, source, tags)
VALUES (
  'VARIABLE_PERIOD_EMA', 1,
  'Variable period EMA using KAMA for adaptive moving average crossover',
  'COMPLEX',
  '[{"id":"close","type":"CLOSE"},{"id":"fastKama","type":"KAMA","input":"close","params":{"period":"${minPeriod}","fastPeriod":2,"slowPeriod":30}},{"id":"slowKama","type":"KAMA","input":"close","params":{"period":"${maxPeriod}","fastPeriod":2,"slowPeriod":30}}]'::jsonb,
  '[{"type":"CROSSED_UP","indicator":"fastKama","params":{"crosses":"slowKama"}}]'::jsonb,
  '[{"type":"CROSSED_DOWN","indicator":"fastKama","params":{"crosses":"slowKama"}}]'::jsonb,
  '[{"name":"minPeriod","type":"INTEGER","min":5,"max":15,"defaultValue":10},{"name":"maxPeriod","type":"INTEGER","min":20,"max":50,"defaultValue":30}]'::jsonb,
  'MIGRATED',
  ARRAY['kama', 'adaptive', 'crossover', 'trend-following', 'phase4']
) ON CONFLICT (name) DO NOTHING;

-- 56. VOLATILITY_STOP
INSERT INTO strategy_specs (name, version, description, complexity, indicators, entry_conditions, exit_conditions, parameters, source, tags)
VALUES (
  'VOLATILITY_STOP', 1,
  'Volatility-based stop strategy using ATR for dynamic stop levels with EMA entry',
  'COMPLEX',
  '[{"id":"close","type":"CLOSE"},{"id":"atr","type":"ATR","params":{"period":"${atrPeriod}"}},{"id":"ema","type":"EMA","input":"close","params":{"period":"${atrPeriod}"}}]'::jsonb,
  '[{"type":"CROSSED_UP","indicator":"close","params":{"crosses":"ema"}}]'::jsonb,
  '[{"type":"STOP_LOSS","params":{"percentage":"${multiplier}"}}]'::jsonb,
  '[{"name":"atrPeriod","type":"INTEGER","min":10,"max":25,"defaultValue":14},{"name":"multiplier","type":"DOUBLE","min":1.5,"max":4.0,"defaultValue":2.5}]'::jsonb,
  'MIGRATED',
  ARRAY['volatility', 'atr', 'stop-loss', 'risk-management', 'phase4']
) ON CONFLICT (name) DO NOTHING;

-- 57. VOLUME_PROFILE
INSERT INTO strategy_specs (name, version, description, complexity, indicators, entry_conditions, exit_conditions, parameters, source, tags)
VALUES (
  'VOLUME_PROFILE', 1,
  'Volume profile strategy using OBV with EMA for volume-weighted trend detection',
  'COMPLEX',
  '[{"id":"obv","type":"OBV"},{"id":"obvEma","type":"EMA","input":"obv","params":{"period":"${period}"}},{"id":"close","type":"CLOSE"},{"id":"priceEma","type":"EMA","input":"close","params":{"period":"${period}"}}]'::jsonb,
  '[{"type":"CROSSED_UP","indicator":"obv","params":{"crosses":"obvEma"}},{"type":"OVER","indicator":"close","params":{"other":"priceEma"}}]'::jsonb,
  '[{"type":"CROSSED_DOWN","indicator":"obv","params":{"crosses":"obvEma"}}]'::jsonb,
  '[{"name":"period","type":"INTEGER","min":10,"max":30,"defaultValue":20}]'::jsonb,
  'MIGRATED',
  ARRAY['volume-profile', 'obv', 'ema', 'compound-entry', 'phase4']
) ON CONFLICT (name) DO NOTHING;

-- 58. VOLUME_PROFILE_DEVIATIONS
INSERT INTO strategy_specs (name, version, description, complexity, indicators, entry_conditions, exit_conditions, parameters, source, tags)
VALUES (
  'VOLUME_PROFILE_DEVIATIONS', 1,
  'Volume profile with standard deviation bands for mean reversion with volume confirmation',
  'COMPLEX',
  '[{"id":"close","type":"CLOSE"},{"id":"volume","type":"VOLUME"},{"id":"volumeSma","type":"SMA","input":"volume","params":{"period":"${period}"}},{"id":"upperBand","type":"BOLLINGER_UPPER","input":"close","params":{"period":"${period}","multiplier":2.0}},{"id":"lowerBand","type":"BOLLINGER_LOWER","input":"close","params":{"period":"${period}","multiplier":2.0}}]'::jsonb,
  '[{"type":"CROSSED_UP","indicator":"close","params":{"crosses":"lowerBand"}},{"type":"OVER","indicator":"volume","params":{"other":"volumeSma"}}]'::jsonb,
  '[{"type":"CROSSED_DOWN","indicator":"close","params":{"crosses":"upperBand"}}]'::jsonb,
  '[{"name":"period","type":"INTEGER","min":15,"max":40,"defaultValue":20}]'::jsonb,
  'MIGRATED',
  ARRAY['volume-profile', 'bollinger', 'mean-reversion', 'volume', 'compound-entry', 'phase4']
) ON CONFLICT (name) DO NOTHING;

-- 59. VOLUME_SPREAD_ANALYSIS
INSERT INTO strategy_specs (name, version, description, complexity, indicators, entry_conditions, exit_conditions, parameters, source, tags)
VALUES (
  'VOLUME_SPREAD_ANALYSIS', 1,
  'Volume spread analysis comparing price spread with volume for trend confirmation',
  'COMPLEX',
  '[{"id":"close","type":"CLOSE"},{"id":"volume","type":"VOLUME"},{"id":"volumeEma","type":"EMA","input":"volume","params":{"period":"${volumePeriod}"}},{"id":"priceEma","type":"EMA","input":"close","params":{"period":"${volumePeriod}"}}]'::jsonb,
  '[{"type":"CROSSED_UP","indicator":"close","params":{"crosses":"priceEma"}},{"type":"OVER","indicator":"volume","params":{"other":"volumeEma"}}]'::jsonb,
  '[{"type":"CROSSED_DOWN","indicator":"close","params":{"crosses":"priceEma"}}]'::jsonb,
  '[{"name":"volumePeriod","type":"INTEGER","min":10,"max":30,"defaultValue":20}]'::jsonb,
  'MIGRATED',
  ARRAY['vsa', 'volume', 'spread', 'trend-confirmation', 'compound-entry', 'phase4']
) ON CONFLICT (name) DO NOTHING;

-- 60. VOLUME_WEIGHTED_MACD
INSERT INTO strategy_specs (name, version, description, complexity, indicators, entry_conditions, exit_conditions, parameters, source, tags)
VALUES (
  'VOLUME_WEIGHTED_MACD', 1,
  'Volume Weighted MACD using MACD with signal line crossover and volume context',
  'COMPLEX',
  '[{"id":"close","type":"CLOSE"},{"id":"macdLine","type":"MACD","input":"close","params":{"shortPeriod":"${shortPeriod}","longPeriod":"${longPeriod}"}},{"id":"signalLine","type":"EMA","input":"macdLine","params":{"period":"${signalPeriod}"}}]'::jsonb,
  '[{"type":"CROSSED_UP","indicator":"macdLine","params":{"crosses":"signalLine"}}]'::jsonb,
  '[{"type":"CROSSED_DOWN","indicator":"macdLine","params":{"crosses":"signalLine"}}]'::jsonb,
  '[{"name":"shortPeriod","type":"INTEGER","min":5,"max":20,"defaultValue":12},{"name":"longPeriod","type":"INTEGER","min":15,"max":50,"defaultValue":26},{"name":"signalPeriod","type":"INTEGER","min":5,"max":15,"defaultValue":9}]'::jsonb,
  'MIGRATED',
  ARRAY['macd', 'volume-weighted', 'momentum', 'crossover', 'phase4']
) ON CONFLICT (name) DO NOTHING;
