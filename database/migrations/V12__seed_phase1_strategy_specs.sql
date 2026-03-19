-- V12__seed_phase1_strategy_specs.sql
-- Phase 1: Seed the first 15 simple strategy specs into the strategy_specs table.
-- These strategies have been validated via YAML configs and deprecated Java implementations.
-- References: Issue #1564 (migrate hardcoded strategies to config)

-- 1. SMA_EMA_CROSSOVER
INSERT INTO strategy_specs (name, version, description, complexity, indicators, entry_conditions, exit_conditions, parameters, source, tags)
VALUES (
  'SMA_EMA_CROSSOVER', 1,
  'Simple Moving Average crosses Exponential Moving Average',
  'SIMPLE',
  '[{"id":"sma","type":"SMA","input":"close","params":{"period":"${smaPeriod}"}},{"id":"ema","type":"EMA","input":"close","params":{"period":"${emaPeriod}"}}]'::jsonb,
  '[{"type":"CROSSED_UP","indicator":"sma","params":{"crosses":"ema"}}]'::jsonb,
  '[{"type":"CROSSED_DOWN","indicator":"sma","params":{"crosses":"ema"}}]'::jsonb,
  '[{"name":"smaPeriod","type":"INTEGER","min":5,"max":50,"defaultValue":20},{"name":"emaPeriod","type":"INTEGER","min":5,"max":50,"defaultValue":50}]'::jsonb,
  'MIGRATED',
  ARRAY['crossover', 'moving-average', 'trend-following', 'phase1']
) ON CONFLICT (name) DO NOTHING;

-- 2. DOUBLE_EMA_CROSSOVER
INSERT INTO strategy_specs (name, version, description, complexity, indicators, entry_conditions, exit_conditions, parameters, source, tags)
VALUES (
  'DOUBLE_EMA_CROSSOVER', 1,
  'Short EMA crosses Long EMA',
  'SIMPLE',
  '[{"id":"shortEma","type":"EMA","input":"close","params":{"period":"${shortEmaPeriod}"}},{"id":"longEma","type":"EMA","input":"close","params":{"period":"${longEmaPeriod}"}}]'::jsonb,
  '[{"type":"CROSSED_UP","indicator":"shortEma","params":{"crosses":"longEma"}}]'::jsonb,
  '[{"type":"CROSSED_DOWN","indicator":"shortEma","params":{"crosses":"longEma"}}]'::jsonb,
  '[{"name":"shortEmaPeriod","type":"INTEGER","min":2,"max":30,"defaultValue":12},{"name":"longEmaPeriod","type":"INTEGER","min":10,"max":100,"defaultValue":26}]'::jsonb,
  'MIGRATED',
  ARRAY['crossover', 'ema', 'trend-following', 'phase1']
) ON CONFLICT (name) DO NOTHING;

-- 3. MACD_CROSSOVER
INSERT INTO strategy_specs (name, version, description, complexity, indicators, entry_conditions, exit_conditions, parameters, source, tags)
VALUES (
  'MACD_CROSSOVER', 1,
  'MACD crosses Signal Line',
  'SIMPLE',
  '[{"id":"macd","type":"MACD","input":"close","params":{"shortPeriod":"${shortEmaPeriod}","longPeriod":"${longEmaPeriod}"}},{"id":"signal","type":"EMA","input":"macd","params":{"period":"${signalPeriod}"}}]'::jsonb,
  '[{"type":"CROSSED_UP","indicator":"macd","params":{"crosses":"signal"}}]'::jsonb,
  '[{"type":"CROSSED_DOWN","indicator":"macd","params":{"crosses":"signal"}}]'::jsonb,
  '[{"name":"shortEmaPeriod","type":"INTEGER","min":8,"max":16,"defaultValue":12},{"name":"longEmaPeriod","type":"INTEGER","min":20,"max":32,"defaultValue":26},{"name":"signalPeriod","type":"INTEGER","min":5,"max":12,"defaultValue":9}]'::jsonb,
  'MIGRATED',
  ARRAY['crossover', 'macd', 'momentum', 'phase1']
) ON CONFLICT (name) DO NOTHING;

-- 4. RSI_EMA_CROSSOVER
INSERT INTO strategy_specs (name, version, description, complexity, indicators, entry_conditions, exit_conditions, parameters, source, tags)
VALUES (
  'RSI_EMA_CROSSOVER', 1,
  'RSI crosses its EMA with overbought/oversold filters',
  'SIMPLE',
  '[{"id":"rsi","type":"RSI","input":"close","params":{"period":"${rsiPeriod}"}},{"id":"rsiEma","type":"EMA","input":"rsi","params":{"period":"${emaPeriod}"}},{"id":"overboughtLevel","type":"CONSTANT","params":{"value":70}},{"id":"oversoldLevel","type":"CONSTANT","params":{"value":30}}]'::jsonb,
  '[{"type":"CROSSED_UP","indicator":"rsi","params":{"crosses":"rsiEma"}},{"type":"UNDER","indicator":"rsi","params":{"value":70}}]'::jsonb,
  '[{"type":"CROSSED_DOWN","indicator":"rsi","params":{"crosses":"rsiEma"}},{"type":"OVER","indicator":"rsi","params":{"value":30}}]'::jsonb,
  '[{"name":"rsiPeriod","type":"INTEGER","min":7,"max":21,"defaultValue":14},{"name":"emaPeriod","type":"INTEGER","min":5,"max":20,"defaultValue":10}]'::jsonb,
  'MIGRATED',
  ARRAY['crossover', 'rsi', 'oscillator', 'phase1']
) ON CONFLICT (name) DO NOTHING;

-- 5. DPO_CROSSOVER
INSERT INTO strategy_specs (name, version, description, complexity, indicators, entry_conditions, exit_conditions, parameters, source, tags)
VALUES (
  'DPO_CROSSOVER', 1,
  'DPO crosses above/below its SMA signal line',
  'SIMPLE',
  '[{"id":"dpo","type":"DPO","params":{"period":"${dpoPeriod}"}},{"id":"dpoSignal","type":"SMA","input":"dpo","params":{"period":"${maPeriod}"}}]'::jsonb,
  '[{"type":"CROSSED_UP","indicator":"dpo","params":{"crosses":"dpoSignal"}}]'::jsonb,
  '[{"type":"CROSSED_DOWN","indicator":"dpo","params":{"crosses":"dpoSignal"}}]'::jsonb,
  '[{"name":"dpoPeriod","type":"INTEGER","min":5,"max":50,"defaultValue":15},{"name":"maPeriod","type":"INTEGER","min":5,"max":50,"defaultValue":10}]'::jsonb,
  'MIGRATED',
  ARRAY['crossover', 'detrended', 'oscillator', 'phase1']
) ON CONFLICT (name) DO NOTHING;

-- 6. ROC_MA_CROSSOVER
INSERT INTO strategy_specs (name, version, description, complexity, indicators, entry_conditions, exit_conditions, parameters, source, tags)
VALUES (
  'ROC_MA_CROSSOVER', 1,
  'Rate of Change crosses its Moving Average',
  'SIMPLE',
  '[{"id":"roc","type":"ROC","input":"close","params":{"period":"${rocPeriod}"}},{"id":"rocMa","type":"SMA","input":"roc","params":{"period":"${maPeriod}"}}]'::jsonb,
  '[{"type":"CROSSED_UP","indicator":"roc","params":{"crosses":"rocMa"}}]'::jsonb,
  '[{"type":"CROSSED_DOWN","indicator":"roc","params":{"crosses":"rocMa"}}]'::jsonb,
  '[{"name":"rocPeriod","type":"INTEGER","min":5,"max":20,"defaultValue":10},{"name":"maPeriod","type":"INTEGER","min":5,"max":30,"defaultValue":14}]'::jsonb,
  'MIGRATED',
  ARRAY['crossover', 'roc', 'momentum', 'phase1']
) ON CONFLICT (name) DO NOTHING;

-- 7. TRIPLE_EMA_CROSSOVER
INSERT INTO strategy_specs (name, version, description, complexity, indicators, entry_conditions, exit_conditions, parameters, source, tags)
VALUES (
  'TRIPLE_EMA_CROSSOVER', 1,
  'Triple EMA crossover strategy using short, medium, and long periods',
  'MEDIUM',
  '[{"id":"shortEma","type":"EMA","input":"close","params":{"period":"${shortEmaPeriod}"}},{"id":"mediumEma","type":"EMA","input":"close","params":{"period":"${mediumEmaPeriod}"}},{"id":"longEma","type":"EMA","input":"close","params":{"period":"${longEmaPeriod}"}}]'::jsonb,
  '[{"type":"ABOVE","indicator":"shortEma","params":{"other":"mediumEma"}},{"type":"ABOVE","indicator":"mediumEma","params":{"other":"longEma"}}]'::jsonb,
  '[{"type":"BELOW","indicator":"shortEma","params":{"other":"mediumEma"}},{"type":"BELOW","indicator":"mediumEma","params":{"other":"longEma"}}]'::jsonb,
  '[{"name":"shortEmaPeriod","type":"INTEGER","min":5,"max":15,"defaultValue":8},{"name":"mediumEmaPeriod","type":"INTEGER","min":10,"max":30,"defaultValue":21},{"name":"longEmaPeriod","type":"INTEGER","min":30,"max":60,"defaultValue":55}]'::jsonb,
  'MIGRATED',
  ARRAY['crossover', 'ema', 'trend-following', 'phase1']
) ON CONFLICT (name) DO NOTHING;

-- 8. DEMA_TEMA_CROSSOVER
INSERT INTO strategy_specs (name, version, description, complexity, indicators, entry_conditions, exit_conditions, parameters, source, tags)
VALUES (
  'DEMA_TEMA_CROSSOVER', 1,
  'Double EMA crosses Triple EMA',
  'SIMPLE',
  '[{"id":"dema","type":"DEMA","input":"close","params":{"period":"${demaPeriod}"}},{"id":"tema","type":"TEMA","input":"close","params":{"period":"${temaPeriod}"}}]'::jsonb,
  '[{"type":"CROSSED_UP","indicator":"dema","params":{"crosses":"tema"}}]'::jsonb,
  '[{"type":"CROSSED_DOWN","indicator":"dema","params":{"crosses":"tema"}}]'::jsonb,
  '[{"name":"demaPeriod","type":"INTEGER","min":5,"max":30,"defaultValue":12},{"name":"temaPeriod","type":"INTEGER","min":10,"max":50,"defaultValue":26}]'::jsonb,
  'MIGRATED',
  ARRAY['crossover', 'dema', 'tema', 'trend-following', 'phase1']
) ON CONFLICT (name) DO NOTHING;

-- 9. MOMENTUM_SMA_CROSSOVER
INSERT INTO strategy_specs (name, version, description, complexity, indicators, entry_conditions, exit_conditions, parameters, source, tags)
VALUES (
  'MOMENTUM_SMA_CROSSOVER', 1,
  'Momentum crosses its SMA',
  'SIMPLE',
  '[{"id":"momentum","type":"ROC","input":"close","params":{"period":"${momentumPeriod}"}},{"id":"momentumSma","type":"SMA","input":"momentum","params":{"period":"${smaPeriod}"}}]'::jsonb,
  '[{"type":"CROSSED_UP","indicator":"momentum","params":{"crosses":"momentumSma"}}]'::jsonb,
  '[{"type":"CROSSED_DOWN","indicator":"momentum","params":{"crosses":"momentumSma"}}]'::jsonb,
  '[{"name":"momentumPeriod","type":"INTEGER","min":5,"max":20,"defaultValue":10},{"name":"smaPeriod","type":"INTEGER","min":5,"max":30,"defaultValue":14}]'::jsonb,
  'MIGRATED',
  ARRAY['crossover', 'momentum', 'trend-following', 'phase1']
) ON CONFLICT (name) DO NOTHING;

-- 10. VWAP_CROSSOVER
INSERT INTO strategy_specs (name, version, description, complexity, indicators, entry_conditions, exit_conditions, parameters, source, tags)
VALUES (
  'VWAP_CROSSOVER', 1,
  'VWAP crossover strategy using price crossing VWAP for intraday trading',
  'SIMPLE',
  '[{"id":"close","type":"CLOSE"},{"id":"vwap","type":"VWAP","params":{"period":"${vwapPeriod}"}},{"id":"priceMa","type":"SMA","input":"close","params":{"period":"${movingAveragePeriod}"}}]'::jsonb,
  '[{"type":"CROSSED_UP","indicator":"close","params":{"crosses":"vwap"}}]'::jsonb,
  '[{"type":"CROSSED_DOWN","indicator":"close","params":{"crosses":"vwap"}}]'::jsonb,
  '[{"name":"vwapPeriod","type":"INTEGER","min":10,"max":30,"defaultValue":20},{"name":"movingAveragePeriod","type":"INTEGER","min":5,"max":20,"defaultValue":10}]'::jsonb,
  'MIGRATED',
  ARRAY['crossover', 'vwap', 'intraday', 'phase1']
) ON CONFLICT (name) DO NOTHING;

-- 11. AWESOME_OSCILLATOR
INSERT INTO strategy_specs (name, version, description, complexity, indicators, entry_conditions, exit_conditions, parameters, source, tags)
VALUES (
  'AWESOME_OSCILLATOR', 1,
  'Awesome Oscillator zero-line crossover - enters when AO crosses above zero',
  'SIMPLE',
  '[{"id":"ao","type":"AWESOME_OSCILLATOR","params":{"shortPeriod":"${shortPeriod}","longPeriod":"${longPeriod}"}}]'::jsonb,
  '[{"type":"CROSSED_UP_CONSTANT","indicator":"ao","params":{"threshold":0}}]'::jsonb,
  '[{"type":"CROSSED_DOWN_CONSTANT","indicator":"ao","params":{"threshold":0}}]'::jsonb,
  '[{"name":"shortPeriod","type":"INTEGER","min":3,"max":10,"defaultValue":5},{"name":"longPeriod","type":"INTEGER","min":20,"max":50,"defaultValue":34}]'::jsonb,
  'MIGRATED',
  ARRAY['oscillator', 'zero-line', 'momentum', 'phase1']
) ON CONFLICT (name) DO NOTHING;

-- 12. OBV_EMA
INSERT INTO strategy_specs (name, version, description, complexity, indicators, entry_conditions, exit_conditions, parameters, source, tags)
VALUES (
  'OBV_EMA', 1,
  'On Balance Volume crosses its EMA',
  'SIMPLE',
  '[{"id":"obv","type":"OBV","input":"close","params":{}},{"id":"obvEma","type":"EMA","input":"obv","params":{"period":"${emaPeriod}"}}]'::jsonb,
  '[{"type":"CROSSED_UP","indicator":"obv","params":{"crosses":"obvEma"}}]'::jsonb,
  '[{"type":"CROSSED_DOWN","indicator":"obv","params":{"crosses":"obvEma"}}]'::jsonb,
  '[{"name":"emaPeriod","type":"INTEGER","min":5,"max":30,"defaultValue":20}]'::jsonb,
  'MIGRATED',
  ARRAY['crossover', 'volume', 'obv', 'phase1']
) ON CONFLICT (name) DO NOTHING;

-- 13. PVT
INSERT INTO strategy_specs (name, version, description, complexity, indicators, entry_conditions, exit_conditions, parameters, source, tags)
VALUES (
  'PVT', 1,
  'Price Volume Trend strategy using PVT indicator with EMA signal crossover',
  'SIMPLE',
  '[{"id":"pvt","type":"PVT"},{"id":"pvtSignal","type":"EMA","input":"pvt","params":{"period":"${period}"}}]'::jsonb,
  '[{"type":"CROSSED_UP","indicator":"pvt","params":{"crosses":"pvtSignal"}}]'::jsonb,
  '[{"type":"CROSSED_DOWN","indicator":"pvt","params":{"crosses":"pvtSignal"}}]'::jsonb,
  '[{"name":"period","type":"INTEGER","min":10,"max":30,"defaultValue":20}]'::jsonb,
  'MIGRATED',
  ARRAY['crossover', 'volume', 'pvt', 'phase1']
) ON CONFLICT (name) DO NOTHING;

-- 14. VPT
INSERT INTO strategy_specs (name, version, description, complexity, indicators, entry_conditions, exit_conditions, parameters, source, tags)
VALUES (
  'VPT', 1,
  'Volume Price Trend strategy using NVI indicator with EMA signal crossover',
  'SIMPLE',
  '[{"id":"nvi","type":"NVI"},{"id":"nviSignal","type":"EMA","input":"nvi","params":{"period":"${period}"}}]'::jsonb,
  '[{"type":"CROSSED_UP","indicator":"nvi","params":{"crosses":"nviSignal"}}]'::jsonb,
  '[{"type":"CROSSED_DOWN","indicator":"nvi","params":{"crosses":"nviSignal"}}]'::jsonb,
  '[{"name":"period","type":"INTEGER","min":10,"max":30,"defaultValue":20}]'::jsonb,
  'MIGRATED',
  ARRAY['crossover', 'volume', 'nvi', 'phase1']
) ON CONFLICT (name) DO NOTHING;

-- 15. CHAIKIN_OSCILLATOR
INSERT INTO strategy_specs (name, version, description, complexity, indicators, entry_conditions, exit_conditions, parameters, source, tags)
VALUES (
  'CHAIKIN_OSCILLATOR', 1,
  'Chaikin Oscillator crosses zero line',
  'SIMPLE',
  '[{"id":"chaikin","type":"CHAIKIN_OSCILLATOR","input":"close","params":{"shortPeriod":"${fastPeriod}","longPeriod":"${slowPeriod}"}},{"id":"zeroLine","type":"CONSTANT","params":{"value":0}}]'::jsonb,
  '[{"type":"CROSSES_ABOVE","indicator":"chaikin","params":{"value":0}}]'::jsonb,
  '[{"type":"CROSSES_BELOW","indicator":"chaikin","params":{"value":0}}]'::jsonb,
  '[{"name":"fastPeriod","type":"INTEGER","min":2,"max":5,"defaultValue":3},{"name":"slowPeriod","type":"INTEGER","min":8,"max":14,"defaultValue":10}]'::jsonb,
  'MIGRATED',
  ARRAY['oscillator', 'zero-line', 'volume', 'chaikin', 'phase1']
) ON CONFLICT (name) DO NOTHING;
