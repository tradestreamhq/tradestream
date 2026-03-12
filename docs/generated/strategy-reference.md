# Strategy Reference

Auto-generated from YAML configs in `src/main/resources/strategies/`.

**Total strategies: 60**

## Overview

| Strategy | Complexity | Indicators | Description |
|----------|-----------|------------|-------------|
| ADX_DMI | SIMPLE | ADX, PLUS_DI, MINUS_DI | ADX with Directional Movement Index - trades strong trends when +DI crosses -DI |
| ADX_STOCHASTIC | SIMPLE | ADX, STOCHASTIC_K | ADX trend filter with Stochastic Oscillator - enters on strong trends when oversold |
| AROON_MFI | MEDIUM | AROON_UP, AROON_DOWN, MFI | Aroon with Money Flow Index - enters on Aroon Up crossing Down when oversold |
| ATR_CCI | SIMPLE | ATR, CCI, PREVIOUS | ATR volatility filter with CCI momentum - enters when CCI oversold and volatility rising |
| ATR_TRAILING_STOP | SIMPLE | CLOSE, PREVIOUS, ATR | ATR-based trailing stop - enters on price momentum, exits on trailing stop loss |
| AWESOME_OSCILLATOR | SIMPLE | AWESOME_OSCILLATOR | Awesome Oscillator zero-line crossover - enters when AO crosses above zero |
| BBAND_WILLIAMS_R | MEDIUM | CLOSE_PRICE, BOLLINGER_UPPER, BOLLINGER_LOWER, WILLIAMS_R | Bollinger Bands with Williams %R - enters at lower band when oversold |
| CHAIKIN_OSCILLATOR | SIMPLE | CHAIKIN_OSCILLATOR, CONSTANT | Chaikin Oscillator crosses zero line |
| CMF_ZERO_LINE | SIMPLE | CMF | Chaikin Money Flow zero-line crossover - enters when CMF crosses above zero |
| CMO_MFI | MEDIUM | CMO, MFI | Chande Momentum Oscillator with Money Flow Index - momentum and volume confirmation |
| DEMA_TEMA_CROSSOVER | SIMPLE | DEMA, TEMA | Double EMA crosses Triple EMA |
| DONCHIAN_BREAKOUT | SIMPLE | CLOSE, DONCHIAN_UPPER, DONCHIAN_LOWER | Donchian Channel breakout - enters when price breaks above highest high |
| DOUBLE_EMA_CROSSOVER | SIMPLE | EMA, EMA | Short EMA crosses Long EMA |
| DOUBLE_TOP_BOTTOM | SIMPLE | CLOSE, EMA | Double Top/Bottom pattern using EMA crossover |
| DPO_CROSSOVER | SIMPLE | DPO, SMA | DPO crosses above/below its SMA signal line |
| ELDER_RAY_MA | SIMPLE | HIGH, LOW, EMA | Elder Ray with EMA - enters when high crosses above EMA (bull power positive) |
| EMA_MACD | SIMPLE | MACD, EMA | EMA-based MACD - enters when MACD crosses above signal line |
| FIBONACCI_RETRACEMENTS | MEDIUM | CLOSE, DONCHIAN_UPPER, DONCHIAN_LOWER, DONCHIAN_MIDDLE | Fibonacci retracement levels for support/resistance trading using price channels |
| FRAMA | MODERATE | FRAMA | Fractal Adaptive Moving Average - enters when price crosses above FRAMA, exits when price crosses below |
| GANN_SWING | SIMPLE | CLOSE, DONCHIAN_UPPER, DONCHIAN_LOWER | Gann swing trading strategy using highest/lowest price channels |
| HEIKEN_ASHI | MODERATE | HEIKEN_ASHI_CLOSE, HEIKEN_ASHI_OPEN | Heiken Ashi - enters when HA close crosses above HA open, exits when HA close crosses below HA open |
| ICHIMOKU_CLOUD | COMPLEX | CLOSE, EMA, EMA, EMA | Ichimoku Cloud strategy using multiple EMAs to simulate Tenkan-Sen and Kijun-Sen crossovers |
| KLINGER_VOLUME | MEDIUM | KLINGER_VOLUME_OSCILLATOR, EMA | Klinger Volume Oscillator with signal line - volume-based trend indicator |
| KST_OSCILLATOR | COMPLEX | CLOSE, ROC, ROC, ROC, ROC, SMA | Know Sure Thing oscillator using weighted ROC indicators with signal line crossover |
| LINEAR_REGRESSION_CHANNELS | MODERATE | LINEAR_REGRESSION_UPPER_CHANNEL, LINEAR_REGRESSION_LOWER_CHANNEL | Linear Regression Channels - enters when price breaks above upper channel, exits when price breaks below lower channel |
| MACD_CROSSOVER | SIMPLE | MACD, EMA | MACD crosses Signal Line |
| MASS_INDEX | MEDIUM | MASS_INDEX | Mass Index reversal bulge strategy - identifies trend reversals via range expansion |
| MOMENTUM_PINBALL | SIMPLE | MOMENTUM, MOMENTUM | Combines short and long term momentum - enters when long momentum is positive and short momentum crosses above zero |
| MOMENTUM_SMA_CROSSOVER | SIMPLE | ROC, SMA | Momentum crosses its SMA |
| OBV_EMA | SIMPLE | OBV, EMA | On Balance Volume crosses its EMA |
| PARABOLIC_SAR | SIMPLE | CLOSE, PARABOLIC_SAR | Parabolic SAR trend-following strategy for stop and reverse signals |
| PIVOT | SIMPLE | CLOSE, TYPICAL_PRICE, DONCHIAN_UPPER, DONCHIAN_LOWER | Pivot point strategy using typical price and Donchian channels for support/resistance |
| PRICE_GAP | SIMPLE | CLOSE, EMA | Price Gap with EMA - enters when price crosses above EMA |
| PRICE_OSCILLATOR_SIGNAL | MODERATE | PRICE_OSCILLATOR, EMA | Price Oscillator Signal - enters when price oscillator crosses above signal line, exits when it crosses below |
| PVT | SIMPLE | PVT, EMA | Price Volume Trend strategy using PVT indicator with EMA signal crossover |
| RAINBOW_OSCILLATOR | MEDIUM | CLOSE, EMA, EMA, EMA | Rainbow oscillator strategy using multiple EMAs of different periods for trend confirmation |
| RANGE_BARS | SIMPLE | CLOSE, ATR, BOLLINGER_UPPER, BOLLINGER_LOWER | Range bars strategy using ATR-based volatility breakouts |
| REGRESSION_CHANNEL | SIMPLE | CLOSE, BOLLINGER_MIDDLE, BOLLINGER_UPPER, BOLLINGER_LOWER | Regression channel mean reversion strategy using Bollinger Bands as channel proxy |
| RENKO_CHART | SIMPLE | CLOSE, ATR, EMA | Renko chart style strategy using ATR-based volatility breakouts for trend following |
| ROC_MA_CROSSOVER | SIMPLE | ROC, SMA | Rate of Change crosses its Moving Average |
| RSI_EMA_CROSSOVER | SIMPLE | RSI, EMA, CONSTANT, CONSTANT | RSI crosses its EMA with overbought/oversold filters |
| RVI | SIMPLE | CLOSE, RSI, SMA | Relative Vigor Index strategy using RSI as vigor proxy with signal line crossover |
| SAR_MFI | MEDIUM | CLOSE, PARABOLIC_SAR, MFI | Parabolic SAR combined with Money Flow Index for trend confirmation with volume |
| SMA_EMA_CROSSOVER | SIMPLE | SMA, EMA | Simple Moving Average crosses Exponential Moving Average |
| SMA_RSI | SIMPLE | CLOSE, SMA, RSI | SMA trend filter combined with RSI overbought/oversold signals |
| STOCHASTIC_EMA | MEDIUM | CLOSE, EMA, STOCHASTIC_K | Stochastic oscillator with EMA trend filter for momentum trading |
| STOCHASTIC_RSI | MEDIUM | RSI, STOCHASTIC_K | Stochastic RSI - enters when oversold, exits when overbought |
| TICK_VOLUME_ANALYSIS | SIMPLE | VOLUME, EMA, CLOSE, EMA | Tick volume analysis strategy using volume indicators with EMA crossover |
| TRIPLE_EMA_CROSSOVER | MEDIUM | EMA, EMA, EMA | Triple EMA crossover strategy using short, medium, and long periods |
| TRIX_SIGNAL_LINE | SIMPLE | TRIX, SMA | TRIX with signal line crossover - enters when TRIX crosses above its SMA signal line |
| VARIABLE_PERIOD_EMA | MEDIUM | CLOSE, KAMA, KAMA | Variable period EMA strategy using KAMA for adaptive moving average crossover |
| VOLATILITY_STOP | SIMPLE | CLOSE, ATR, EMA | Volatility-based stop strategy using ATR for dynamic stop levels |
| VOLUME_BREAKOUT | SIMPLE | CLOSE, VOLUME, SMA, SMA | Volume breakout strategy detecting high volume moves with price confirmation |
| VOLUME_PROFILE | SIMPLE | OBV, EMA, CLOSE, EMA | Volume profile strategy using OBV with EMA for volume-weighted trend detection |
| VOLUME_PROFILE_DEVIATIONS | MEDIUM | CLOSE, VOLUME, SMA, BOLLINGER_UPPER, BOLLINGER_LOWER | Volume profile with standard deviation bands for mean reversion trading |
| VOLUME_SPREAD_ANALYSIS | SIMPLE | CLOSE, VOLUME, EMA, EMA | Volume spread analysis strategy comparing price spread with volume for trend confirmation |
| VOLUME_WEIGHTED_MACD | MODERATE | VOLUME_WEIGHTED_MACD, EMA | Volume Weighted MACD - enters when MACD line crosses above signal line, exits when it crosses below |
| VPT | SIMPLE | NVI, EMA | Volume Price Trend strategy using NVI indicator with EMA signal crossover |
| VWAP_CROSSOVER | SIMPLE | CLOSE, VWAP, SMA | VWAP crossover strategy using price crossing VWAP for intraday trading |
| VWAP_MEAN_REVERSION | MEDIUM | CLOSE, VWAP, BOLLINGER_UPPER, BOLLINGER_LOWER | VWAP mean reversion strategy buying below VWAP and selling above for range trading |

## Strategy Details

### ADX_DMI

**File:** `adx_dmi.yaml`  
**Complexity:** SIMPLE  
**Description:** ADX with Directional Movement Index - trades strong trends when +DI crosses -DI

#### Indicators

| ID | Type | Input | Parameters |
|----|------|-------|------------|
| adx | ADX | N/A | period=${adxPeriod} |
| plusDI | PLUS_DI | N/A | period=${diPeriod} |
| minusDI | MINUS_DI | N/A | period=${diPeriod} |

#### Entry Conditions

- **OVER_CONSTANT** on `adx` (threshold=25)
- **CROSSED_UP** on `plusDI` (crosses=minusDI)

#### Exit Conditions

- **CROSSED_DOWN** on `plusDI` (crosses=minusDI)

#### Parameters

| Name | Type | Min | Max | Default |
|------|------|-----|-----|---------|
| adxPeriod | INTEGER | 10 | 30 | 14 |
| diPeriod | INTEGER | 10 | 30 | 14 |

---

### ADX_STOCHASTIC

**File:** `adx_stochastic.yaml`  
**Complexity:** SIMPLE  
**Description:** ADX trend filter with Stochastic Oscillator - enters on strong trends when oversold

#### Indicators

| ID | Type | Input | Parameters |
|----|------|-------|------------|
| adx | ADX | N/A | period=${adxPeriod} |
| stochasticK | STOCHASTIC_K | N/A | period=${stochasticKPeriod} |

#### Entry Conditions

- **OVER_CONSTANT** on `adx` (threshold=20)
- **UNDER_CONSTANT** on `stochasticK` (threshold=${oversoldThreshold})

#### Exit Conditions

- **UNDER_CONSTANT** on `adx` (threshold=20)
- **OVER_CONSTANT** on `stochasticK` (threshold=${overboughtThreshold})

#### Parameters

| Name | Type | Min | Max | Default |
|------|------|-----|-----|---------|
| adxPeriod | INTEGER | 10 | 30 | 14 |
| stochasticKPeriod | INTEGER | 5 | 21 | 14 |
| overboughtThreshold | INTEGER | 70 | 90 | 80 |
| oversoldThreshold | INTEGER | 10 | 30 | 20 |

---

### AROON_MFI

**File:** `aroon_mfi.yaml`  
**Complexity:** MEDIUM  
**Description:** Aroon with Money Flow Index - enters on Aroon Up crossing Down when oversold

#### Indicators

| ID | Type | Input | Parameters |
|----|------|-------|------------|
| aroonUp | AROON_UP | N/A | period=${aroonPeriod} |
| aroonDown | AROON_DOWN | N/A | period=${aroonPeriod} |
| mfi | MFI | N/A | period=${mfiPeriod} |

#### Entry Conditions

- **CROSSED_UP** on `aroonUp` (crosses=aroonDown)
- **UNDER_CONSTANT** on `mfi` (threshold=${oversoldThreshold})

#### Exit Conditions

- **OVER** on `aroonUp` (other=aroonDown)
- **OVER_CONSTANT** on `mfi` (threshold=${overboughtThreshold})

#### Parameters

| Name | Type | Min | Max | Default |
|------|------|-----|-----|---------|
| aroonPeriod | INTEGER | 15 | 35 | 25 |
| mfiPeriod | INTEGER | 7 | 21 | 14 |
| overboughtThreshold | INTEGER | 70 | 90 | 80 |
| oversoldThreshold | INTEGER | 10 | 30 | 20 |

---

### ATR_CCI

**File:** `atr_cci.yaml`  
**Complexity:** SIMPLE  
**Description:** ATR volatility filter with CCI momentum - enters when CCI oversold and volatility rising

#### Indicators

| ID | Type | Input | Parameters |
|----|------|-------|------------|
| atr | ATR | N/A | period=${atrPeriod} |
| cci | CCI | N/A | period=${cciPeriod} |
| previousAtr | PREVIOUS | atr | n=1 |

#### Entry Conditions

- **OVER_CONSTANT** on `cci` (threshold=-100)
- **OVER** on `atr` (other=previousAtr)

#### Exit Conditions

- **UNDER_CONSTANT** on `cci` (threshold=100)
- **UNDER** on `atr` (other=previousAtr)

#### Parameters

| Name | Type | Min | Max | Default |
|------|------|-----|-----|---------|
| atrPeriod | INTEGER | 7 | 21 | 14 |
| cciPeriod | INTEGER | 14 | 28 | 20 |

---

### ATR_TRAILING_STOP

**File:** `atr_trailing_stop.yaml`  
**Complexity:** SIMPLE  
**Description:** ATR-based trailing stop - enters on price momentum, exits on trailing stop loss

#### Indicators

| ID | Type | Input | Parameters |
|----|------|-------|------------|
| closePrice | CLOSE | N/A |  |
| previousClose | PREVIOUS | closePrice |  |
| atr | ATR | N/A | period=${atrPeriod} |

#### Entry Conditions

- **ABOVE** on `closePrice` (other=previousClose)

#### Exit Conditions

- **TRAILING_STOP_LOSS** on `?` (percentage=${multiplier})

#### Parameters

| Name | Type | Min | Max | Default |
|------|------|-----|-----|---------|
| atrPeriod | INTEGER | 5 | 30 | 14 |
| multiplier | DOUBLE | 1.0 | 5.0 | 3.0 |

---

### AWESOME_OSCILLATOR

**File:** `awesome_oscillator.yaml`  
**Complexity:** SIMPLE  
**Description:** Awesome Oscillator zero-line crossover - enters when AO crosses above zero

#### Indicators

| ID | Type | Input | Parameters |
|----|------|-------|------------|
| ao | AWESOME_OSCILLATOR | N/A | longPeriod=${longPeriod}, shortPeriod=${shortPeriod} |

#### Entry Conditions

- **CROSSED_UP_CONSTANT** on `ao` (threshold=0)

#### Exit Conditions

- **CROSSED_DOWN_CONSTANT** on `ao` (threshold=0)

#### Parameters

| Name | Type | Min | Max | Default |
|------|------|-----|-----|---------|
| shortPeriod | INTEGER | 3 | 10 | 5 |
| longPeriod | INTEGER | 20 | 50 | 34 |

---

### BBAND_WILLIAMS_R

**File:** `bband_williams_r.yaml`  
**Complexity:** MEDIUM  
**Description:** Bollinger Bands with Williams %R - enters at lower band when oversold

#### Indicators

| ID | Type | Input | Parameters |
|----|------|-------|------------|
| closePrice | CLOSE_PRICE | N/A |  |
| bbUpper | BOLLINGER_UPPER | N/A | k=${stdDevMultiplier}, period=${bbandsPeriod} |
| bbLower | BOLLINGER_LOWER | N/A | k=${stdDevMultiplier}, period=${bbandsPeriod} |
| williamsR | WILLIAMS_R | N/A | period=${wrPeriod} |

#### Entry Conditions

- **UNDER_INDICATOR** on `closePrice` (other=bbLower)
- **UNDER_CONSTANT** on `williamsR` (threshold=-80)

#### Exit Conditions

- **OVER_INDICATOR** on `closePrice` (other=bbUpper)
- **OVER_CONSTANT** on `williamsR` (threshold=-20)

#### Parameters

| Name | Type | Min | Max | Default |
|------|------|-----|-----|---------|
| bbandsPeriod | INTEGER | 10 | 30 | 20 |
| wrPeriod | INTEGER | 7 | 21 | 14 |
| stdDevMultiplier | DOUBLE | 1.5 | 3.0 | 2.0 |

---

### CHAIKIN_OSCILLATOR

**File:** `chaikin_oscillator.yaml`  
**Complexity:** SIMPLE  
**Description:** Chaikin Oscillator crosses zero line

#### Indicators

| ID | Type | Input | Parameters |
|----|------|-------|------------|
| chaikin | CHAIKIN_OSCILLATOR | close | longPeriod=${slowPeriod}, shortPeriod=${fastPeriod} |
| zeroLine | CONSTANT | N/A | value=0 |

#### Entry Conditions

- **CROSSES_ABOVE** on `chaikin` (value=0)

#### Exit Conditions

- **CROSSES_BELOW** on `chaikin` (value=0)

#### Parameters

| Name | Type | Min | Max | Default |
|------|------|-----|-----|---------|
| fastPeriod | INTEGER | 2 | 5 | 3 |
| slowPeriod | INTEGER | 8 | 14 | 10 |

---

### CMF_ZERO_LINE

**File:** `cmf_zero_line.yaml`  
**Complexity:** SIMPLE  
**Description:** Chaikin Money Flow zero-line crossover - enters when CMF crosses above zero

#### Indicators

| ID | Type | Input | Parameters |
|----|------|-------|------------|
| cmf | CMF | N/A | period=${period} |

#### Entry Conditions

- **CROSSED_UP** on `cmf` (value=0)

#### Exit Conditions

- **CROSSED_DOWN** on `cmf` (value=0)

#### Parameters

| Name | Type | Min | Max | Default |
|------|------|-----|-----|---------|
| period | INTEGER | 10 | 50 | 20 |

---

### CMO_MFI

**File:** `cmo_mfi.yaml`  
**Complexity:** MEDIUM  
**Description:** Chande Momentum Oscillator with Money Flow Index - momentum and volume confirmation

#### Indicators

| ID | Type | Input | Parameters |
|----|------|-------|------------|
| cmo | CMO | N/A | period=${cmoPeriod} |
| mfi | MFI | N/A | period=${mfiPeriod} |

#### Entry Conditions

- **CROSSED_UP** on `cmo` (value=0)
- **UNDER_CONSTANT** on `mfi` (threshold=20)

#### Exit Conditions

- **CROSSED_DOWN** on `cmo` (value=0)
- **OVER_CONSTANT** on `mfi` (threshold=80)

#### Parameters

| Name | Type | Min | Max | Default |
|------|------|-----|-----|---------|
| cmoPeriod | INTEGER | 7 | 21 | 14 |
| mfiPeriod | INTEGER | 7 | 21 | 14 |

---

### DEMA_TEMA_CROSSOVER

**File:** `dema_tema_crossover.yaml`  
**Complexity:** SIMPLE  
**Description:** Double EMA crosses Triple EMA

#### Indicators

| ID | Type | Input | Parameters |
|----|------|-------|------------|
| dema | DEMA | close | period=${demaPeriod} |
| tema | TEMA | close | period=${temaPeriod} |

#### Entry Conditions

- **CROSSED_UP** on `dema` (crosses=tema)

#### Exit Conditions

- **CROSSED_DOWN** on `dema` (crosses=tema)

#### Parameters

| Name | Type | Min | Max | Default |
|------|------|-----|-----|---------|
| demaPeriod | INTEGER | 5 | 30 | 12 |
| temaPeriod | INTEGER | 10 | 50 | 26 |

---

### DONCHIAN_BREAKOUT

**File:** `donchian_breakout.yaml`  
**Complexity:** SIMPLE  
**Description:** Donchian Channel breakout - enters when price breaks above highest high

#### Indicators

| ID | Type | Input | Parameters |
|----|------|-------|------------|
| closePrice | CLOSE | N/A |  |
| upperChannel | DONCHIAN_UPPER | N/A | period=${donchianPeriod} |
| lowerChannel | DONCHIAN_LOWER | N/A | period=${donchianPeriod} |

#### Entry Conditions

- **OVER_INDICATOR** on `closePrice` (other=upperChannel)

#### Exit Conditions

- **UNDER_INDICATOR** on `closePrice` (other=lowerChannel)

#### Parameters

| Name | Type | Min | Max | Default |
|------|------|-----|-----|---------|
| donchianPeriod | INTEGER | 10 | 50 | 20 |

---

### DOUBLE_EMA_CROSSOVER

**File:** `double_ema_crossover.yaml`  
**Complexity:** SIMPLE  
**Description:** Short EMA crosses Long EMA

#### Indicators

| ID | Type | Input | Parameters |
|----|------|-------|------------|
| shortEma | EMA | close | period=${shortEmaPeriod} |
| longEma | EMA | close | period=${longEmaPeriod} |

#### Entry Conditions

- **CROSSED_UP** on `shortEma` (crosses=longEma)

#### Exit Conditions

- **CROSSED_DOWN** on `shortEma` (crosses=longEma)

#### Parameters

| Name | Type | Min | Max | Default |
|------|------|-----|-----|---------|
| shortEmaPeriod | INTEGER | 5 | 20 | 10 |
| longEmaPeriod | INTEGER | 20 | 50 | 30 |

---

### DOUBLE_TOP_BOTTOM

**File:** `double_top_bottom.yaml`  
**Complexity:** SIMPLE  
**Description:** Double Top/Bottom pattern using EMA crossover

#### Indicators

| ID | Type | Input | Parameters |
|----|------|-------|------------|
| closePrice | CLOSE | N/A |  |
| ema | EMA | N/A | period=${period} |

#### Entry Conditions

- **CROSSED_UP** on `closePrice` (crosses=ema)

#### Exit Conditions

- **CROSSED_DOWN** on `closePrice` (crosses=ema)

#### Parameters

| Name | Type | Min | Max | Default |
|------|------|-----|-----|---------|
| period | INTEGER | 10 | 50 | 20 |

---

### DPO_CROSSOVER

**File:** `dpo_crossover.yaml`  
**Complexity:** SIMPLE  
**Description:** DPO crosses above/below its SMA signal line

#### Indicators

| ID | Type | Input | Parameters |
|----|------|-------|------------|
| dpo | DPO | N/A | period=${dpoPeriod} |
| dpoSignal | SMA | dpo | period=${maPeriod} |

#### Entry Conditions

- **CROSSED_UP** on `dpo` (crosses=dpoSignal)

#### Exit Conditions

- **CROSSED_DOWN** on `dpo` (crosses=dpoSignal)

#### Parameters

| Name | Type | Min | Max | Default |
|------|------|-----|-----|---------|
| dpoPeriod | INTEGER | 5 | 50 | 15 |
| maPeriod | INTEGER | 5 | 50 | 10 |

---

### ELDER_RAY_MA

**File:** `elder_ray_ma.yaml`  
**Complexity:** SIMPLE  
**Description:** Elder Ray with EMA - enters when high crosses above EMA (bull power positive)

#### Indicators

| ID | Type | Input | Parameters |
|----|------|-------|------------|
| highPrice | HIGH | N/A |  |
| lowPrice | LOW | N/A |  |
| ema | EMA | N/A | period=${emaPeriod} |

#### Entry Conditions

- **CROSSED_UP** on `highPrice` (crosses=ema)

#### Exit Conditions

- **CROSSED_DOWN** on `lowPrice` (crosses=ema)

#### Parameters

| Name | Type | Min | Max | Default |
|------|------|-----|-----|---------|
| emaPeriod | INTEGER | 10 | 30 | 20 |

---

### EMA_MACD

**File:** `ema_macd.yaml`  
**Complexity:** SIMPLE  
**Description:** EMA-based MACD - enters when MACD crosses above signal line

#### Indicators

| ID | Type | Input | Parameters |
|----|------|-------|------------|
| macd | MACD | N/A | longPeriod=${longEmaPeriod}, shortPeriod=${shortEmaPeriod} |
| signalLine | EMA | macd | period=${signalPeriod} |

#### Entry Conditions

- **CROSSED_UP** on `macd` (crosses=signalLine)

#### Exit Conditions

- **CROSSED_DOWN** on `macd` (crosses=signalLine)

#### Parameters

| Name | Type | Min | Max | Default |
|------|------|-----|-----|---------|
| shortEmaPeriod | INTEGER | 8 | 16 | 12 |
| longEmaPeriod | INTEGER | 20 | 32 | 26 |
| signalPeriod | INTEGER | 6 | 12 | 9 |

---

### FIBONACCI_RETRACEMENTS

**File:** `fibonacci_retracements.yaml`  
**Complexity:** MEDIUM  
**Description:** Fibonacci retracement levels for support/resistance trading using price channels

#### Indicators

| ID | Type | Input | Parameters |
|----|------|-------|------------|
| close | CLOSE | N/A |  |
| high | DONCHIAN_UPPER | N/A | period=${period} |
| low | DONCHIAN_LOWER | N/A | period=${period} |
| middle | DONCHIAN_MIDDLE | N/A | period=${period} |

#### Entry Conditions

- **CROSSED_UP** on `close` (crosses=low)

#### Exit Conditions

- **CROSSED_DOWN** on `close` (crosses=high)

#### Parameters

| Name | Type | Min | Max | Default |
|------|------|-----|-----|---------|
| period | INTEGER | 20 | 100 | 50 |

---

### FRAMA

**File:** `frama.yaml`  
**Complexity:** MODERATE  
**Description:** Fractal Adaptive Moving Average - enters when price crosses above FRAMA, exits when price crosses below

#### Indicators

| ID | Type | Input | Parameters |
|----|------|-------|------------|
| frama | FRAMA | N/A | alpha=${alpha}, fc=${fc}, sc=${sc} |

#### Entry Conditions

- **CROSSED_UP** on `close` (crosses=frama)

#### Exit Conditions

- **CROSSED_DOWN** on `close` (crosses=frama)

#### Parameters

| Name | Type | Min | Max | Default |
|------|------|-----|-----|---------|
| sc | DOUBLE | 0.1 | 2.0 | 0.5 |
| fc | INTEGER | 5 | 50 | 20 |
| alpha | DOUBLE | 0.1 | 1.0 | 0.5 |

---

### GANN_SWING

**File:** `gann_swing.yaml`  
**Complexity:** SIMPLE  
**Description:** Gann swing trading strategy using highest/lowest price channels

#### Indicators

| ID | Type | Input | Parameters |
|----|------|-------|------------|
| close | CLOSE | N/A |  |
| swingHigh | DONCHIAN_UPPER | N/A | period=${gannPeriod} |
| swingLow | DONCHIAN_LOWER | N/A | period=${gannPeriod} |

#### Entry Conditions

- **CROSSED_UP** on `close` (crosses=swingHigh)

#### Exit Conditions

- **CROSSED_DOWN** on `close` (crosses=swingLow)

#### Parameters

| Name | Type | Min | Max | Default |
|------|------|-----|-----|---------|
| gannPeriod | INTEGER | 5 | 30 | 10 |

---

### HEIKEN_ASHI

**File:** `heiken_ashi.yaml`  
**Complexity:** MODERATE  
**Description:** Heiken Ashi - enters when HA close crosses above HA open, exits when HA close crosses below HA open

#### Indicators

| ID | Type | Input | Parameters |
|----|------|-------|------------|
| heikenAshiClose | HEIKEN_ASHI_CLOSE | N/A | period=${period} |
| heikenAshiOpen | HEIKEN_ASHI_OPEN | N/A | period=${period} |

#### Entry Conditions

- **CROSSED_UP** on `heikenAshiClose` (crosses=heikenAshiOpen)

#### Exit Conditions

- **CROSSED_DOWN** on `heikenAshiClose` (crosses=heikenAshiOpen)

#### Parameters

| Name | Type | Min | Max | Default |
|------|------|-----|-----|---------|
| period | INTEGER | 2 | 30 | 14 |

---

### ICHIMOKU_CLOUD

**File:** `ichimoku_cloud.yaml`  
**Complexity:** COMPLEX  
**Description:** Ichimoku Cloud strategy using multiple EMAs to simulate Tenkan-Sen and Kijun-Sen crossovers

#### Indicators

| ID | Type | Input | Parameters |
|----|------|-------|------------|
| close | CLOSE | N/A |  |
| tenkanSen | EMA | close | period=${tenkanSenPeriod} |
| kijunSen | EMA | close | period=${kijunSenPeriod} |
| senkouSpanB | EMA | close | period=${senkouSpanBPeriod} |

#### Entry Conditions

- **CROSSED_UP** on `tenkanSen` (crosses=kijunSen)
- **OVER** on `close` (other=senkouSpanB)

#### Exit Conditions

- **CROSSED_DOWN** on `tenkanSen` (crosses=kijunSen)

#### Parameters

| Name | Type | Min | Max | Default |
|------|------|-----|-----|---------|
| tenkanSenPeriod | INTEGER | 7 | 12 | 9 |
| kijunSenPeriod | INTEGER | 20 | 30 | 26 |
| senkouSpanBPeriod | INTEGER | 45 | 60 | 52 |
| chikouSpanPeriod | INTEGER | 20 | 30 | 26 |

---

### KLINGER_VOLUME

**File:** `klinger_volume.yaml`  
**Complexity:** MEDIUM  
**Description:** Klinger Volume Oscillator with signal line - volume-based trend indicator

#### Indicators

| ID | Type | Input | Parameters |
|----|------|-------|------------|
| kvo | KLINGER_VOLUME_OSCILLATOR | N/A | longPeriod=${longPeriod}, shortPeriod=${shortPeriod} |
| signalLine | EMA | kvo | period=${signalPeriod} |

#### Entry Conditions

- **CROSSED_UP** on `kvo` (crosses=signalLine)

#### Exit Conditions

- **CROSSED_DOWN** on `kvo` (crosses=signalLine)

#### Parameters

| Name | Type | Min | Max | Default |
|------|------|-----|-----|---------|
| shortPeriod | INTEGER | 5 | 20 | 10 |
| longPeriod | INTEGER | 20 | 50 | 35 |
| signalPeriod | INTEGER | 5 | 15 | 10 |

---

### KST_OSCILLATOR

**File:** `kst_oscillator.yaml`  
**Complexity:** COMPLEX  
**Description:** Know Sure Thing oscillator using weighted ROC indicators with signal line crossover

#### Indicators

| ID | Type | Input | Parameters |
|----|------|-------|------------|
| close | CLOSE | N/A |  |
| roc1 | ROC | close | period=${rma1Period} |
| roc2 | ROC | close | period=${rma2Period} |
| roc3 | ROC | close | period=${rma3Period} |
| roc4 | ROC | close | period=${rma4Period} |
| kstSignal | SMA | roc1 | period=${signalPeriod} |

#### Entry Conditions

- **CROSSED_UP** on `roc1` (crosses=kstSignal)

#### Exit Conditions

- **CROSSED_DOWN** on `roc1` (crosses=kstSignal)

#### Parameters

| Name | Type | Min | Max | Default |
|------|------|-----|-----|---------|
| rma1Period | INTEGER | 8 | 12 | 10 |
| rma2Period | INTEGER | 13 | 17 | 15 |
| rma3Period | INTEGER | 18 | 22 | 20 |
| rma4Period | INTEGER | 28 | 32 | 30 |
| signalPeriod | INTEGER | 7 | 11 | 9 |

---

### LINEAR_REGRESSION_CHANNELS

**File:** `linear_regression_channels.yaml`  
**Complexity:** MODERATE  
**Description:** Linear Regression Channels - enters when price breaks above upper channel, exits when price breaks below lower channel

#### Indicators

| ID | Type | Input | Parameters |
|----|------|-------|------------|
| lrcUpper | LINEAR_REGRESSION_UPPER_CHANNEL | N/A | multiplier=${multiplier}, period=${period} |
| lrcLower | LINEAR_REGRESSION_LOWER_CHANNEL | N/A | multiplier=${multiplier}, period=${period} |

#### Entry Conditions

- **CROSSED_UP** on `close` (crosses=lrcUpper)

#### Exit Conditions

- **CROSSED_DOWN** on `close` (crosses=lrcLower)

#### Parameters

| Name | Type | Min | Max | Default |
|------|------|-----|-----|---------|
| period | INTEGER | 10 | 50 | 20 |
| multiplier | DOUBLE | 1.0 | 3.0 | 2.0 |

---

### MACD_CROSSOVER

**File:** `macd_crossover.yaml`  
**Complexity:** SIMPLE  
**Description:** MACD crosses Signal Line

#### Indicators

| ID | Type | Input | Parameters |
|----|------|-------|------------|
| macd | MACD | close | longPeriod=${longEmaPeriod}, shortPeriod=${shortEmaPeriod} |
| signal | EMA | macd | period=${signalPeriod} |

#### Entry Conditions

- **CROSSED_UP** on `macd` (crosses=signal)

#### Exit Conditions

- **CROSSED_DOWN** on `macd` (crosses=signal)

#### Parameters

| Name | Type | Min | Max | Default |
|------|------|-----|-----|---------|
| shortEmaPeriod | INTEGER | 8 | 16 | 12 |
| longEmaPeriod | INTEGER | 20 | 32 | 26 |
| signalPeriod | INTEGER | 5 | 12 | 9 |

---

### MASS_INDEX

**File:** `mass_index.yaml`  
**Complexity:** MEDIUM  
**Description:** Mass Index reversal bulge strategy - identifies trend reversals via range expansion

#### Indicators

| ID | Type | Input | Parameters |
|----|------|-------|------------|
| massIndex | MASS_INDEX | N/A | emaPeriod=${emaPeriod}, sumPeriod=${sumPeriod} |

#### Entry Conditions

- **CROSSED_DOWN_CONSTANT** on `massIndex` (threshold=26.5)

#### Exit Conditions

- **CROSSED_UP_CONSTANT** on `massIndex` (threshold=27)
- **CROSSED_DOWN_CONSTANT** on `massIndex` (threshold=25)

#### Parameters

| Name | Type | Min | Max | Default |
|------|------|-----|-----|---------|
| emaPeriod | INTEGER | 5 | 15 | 9 |
| sumPeriod | INTEGER | 15 | 35 | 25 |

---

### MOMENTUM_PINBALL

**File:** `momentum_pinball.yaml`  
**Complexity:** SIMPLE  
**Description:** Combines short and long term momentum - enters when long momentum is positive and short momentum crosses above zero

#### Indicators

| ID | Type | Input | Parameters |
|----|------|-------|------------|
| shortMomentum | MOMENTUM | close | period=${shortPeriod} |
| longMomentum | MOMENTUM | close | period=${longPeriod} |

#### Entry Conditions

- **OVER_CONSTANT** on `longMomentum` (threshold=0)
- **CROSSED_UP** on `shortMomentum` (value=0)

#### Exit Conditions

- **UNDER_CONSTANT** on `longMomentum` (threshold=0)
- **CROSSED_DOWN** on `shortMomentum` (value=0)

#### Parameters

| Name | Type | Min | Max | Default |
|------|------|-----|-----|---------|
| shortPeriod | INTEGER | 2 | 30 | 10 |
| longPeriod | INTEGER | 5 | 60 | 20 |

---

### MOMENTUM_SMA_CROSSOVER

**File:** `momentum_sma_crossover.yaml`  
**Complexity:** SIMPLE  
**Description:** Momentum crosses its SMA

#### Indicators

| ID | Type | Input | Parameters |
|----|------|-------|------------|
| momentum | ROC | close | period=${momentumPeriod} |
| momentumSma | SMA | momentum | period=${smaPeriod} |

#### Entry Conditions

- **CROSSED_UP** on `momentum` (crosses=momentumSma)

#### Exit Conditions

- **CROSSED_DOWN** on `momentum` (crosses=momentumSma)

#### Parameters

| Name | Type | Min | Max | Default |
|------|------|-----|-----|---------|
| momentumPeriod | INTEGER | 5 | 20 | 10 |
| smaPeriod | INTEGER | 5 | 30 | 14 |

---

### OBV_EMA

**File:** `obv_ema.yaml`  
**Complexity:** SIMPLE  
**Description:** On Balance Volume crosses its EMA

#### Indicators

| ID | Type | Input | Parameters |
|----|------|-------|------------|
| obv | OBV | close |  |
| obvEma | EMA | obv | period=${emaPeriod} |

#### Entry Conditions

- **CROSSED_UP** on `obv` (crosses=obvEma)

#### Exit Conditions

- **CROSSED_DOWN** on `obv` (crosses=obvEma)

#### Parameters

| Name | Type | Min | Max | Default |
|------|------|-----|-----|---------|
| emaPeriod | INTEGER | 5 | 30 | 20 |

---

### PARABOLIC_SAR

**File:** `parabolic_sar.yaml`  
**Complexity:** SIMPLE  
**Description:** Parabolic SAR trend-following strategy for stop and reverse signals

#### Indicators

| ID | Type | Input | Parameters |
|----|------|-------|------------|
| close | CLOSE | N/A |  |
| sar | PARABOLIC_SAR | N/A |  |

#### Entry Conditions

- **CROSSED_UP** on `close` (crosses=sar)

#### Exit Conditions

- **CROSSED_DOWN** on `close` (crosses=sar)

#### Parameters

| Name | Type | Min | Max | Default |
|------|------|-----|-----|---------|
| accelerationFactorStart | DOUBLE | 0.01 | 0.03 | 0.02 |
| accelerationFactorIncrement | DOUBLE | 0.01 | 0.03 | 0.02 |
| accelerationFactorMax | DOUBLE | 0.15 | 0.25 | 0.2 |

---

### PIVOT

**File:** `pivot.yaml`  
**Complexity:** SIMPLE  
**Description:** Pivot point strategy using typical price and Donchian channels for support/resistance

#### Indicators

| ID | Type | Input | Parameters |
|----|------|-------|------------|
| close | CLOSE | N/A |  |
| typicalPrice | TYPICAL_PRICE | N/A |  |
| pivotHigh | DONCHIAN_UPPER | N/A | period=${period} |
| pivotLow | DONCHIAN_LOWER | N/A | period=${period} |

#### Entry Conditions

- **CROSSED_UP** on `close` (crosses=pivotLow)

#### Exit Conditions

- **CROSSED_DOWN** on `close` (crosses=pivotHigh)

#### Parameters

| Name | Type | Min | Max | Default |
|------|------|-----|-----|---------|
| period | INTEGER | 5 | 20 | 10 |

---

### PRICE_GAP

**File:** `price_gap.yaml`  
**Complexity:** SIMPLE  
**Description:** Price Gap with EMA - enters when price crosses above EMA

#### Indicators

| ID | Type | Input | Parameters |
|----|------|-------|------------|
| closePrice | CLOSE | N/A |  |
| ema | EMA | N/A | period=${period} |

#### Entry Conditions

- **CROSSED_UP** on `closePrice` (crosses=ema)

#### Exit Conditions

- **CROSSED_DOWN** on `closePrice` (crosses=ema)

#### Parameters

| Name | Type | Min | Max | Default |
|------|------|-----|-----|---------|
| period | INTEGER | 5 | 20 | 10 |

---

### PRICE_OSCILLATOR_SIGNAL

**File:** `price_oscillator_signal.yaml`  
**Complexity:** MODERATE  
**Description:** Price Oscillator Signal - enters when price oscillator crosses above signal line, exits when it crosses below

#### Indicators

| ID | Type | Input | Parameters |
|----|------|-------|------------|
| priceOscillator | PRICE_OSCILLATOR | N/A | fastPeriod=${fastPeriod}, slowPeriod=${slowPeriod} |
| signalLine | EMA | N/A | period=${signalPeriod}, source=priceOscillator |

#### Entry Conditions

- **CROSSED_UP** on `priceOscillator` (crosses=signalLine)

#### Exit Conditions

- **CROSSED_DOWN** on `priceOscillator` (crosses=signalLine)

#### Parameters

| Name | Type | Min | Max | Default |
|------|------|-----|-----|---------|
| fastPeriod | INTEGER | 5 | 20 | 10 |
| slowPeriod | INTEGER | 10 | 50 | 20 |
| signalPeriod | INTEGER | 5 | 20 | 9 |

---

### PVT

**File:** `pvt.yaml`  
**Complexity:** SIMPLE  
**Description:** Price Volume Trend strategy using PVT indicator with EMA signal crossover

#### Indicators

| ID | Type | Input | Parameters |
|----|------|-------|------------|
| pvt | PVT | N/A |  |
| pvtSignal | EMA | pvt | period=${period} |

#### Entry Conditions

- **CROSSED_UP** on `pvt` (crosses=pvtSignal)

#### Exit Conditions

- **CROSSED_DOWN** on `pvt` (crosses=pvtSignal)

#### Parameters

| Name | Type | Min | Max | Default |
|------|------|-----|-----|---------|
| period | INTEGER | 10 | 30 | 20 |

---

### RAINBOW_OSCILLATOR

**File:** `rainbow_oscillator.yaml`  
**Complexity:** MEDIUM  
**Description:** Rainbow oscillator strategy using multiple EMAs of different periods for trend confirmation

#### Indicators

| ID | Type | Input | Parameters |
|----|------|-------|------------|
| close | CLOSE | N/A |  |
| ema1 | EMA | close | period=5 |
| ema2 | EMA | close | period=10 |
| ema3 | EMA | close | period=20 |

#### Entry Conditions

- **OVER** on `ema1` (other=ema2)
- **OVER** on `ema2` (other=ema3)

#### Exit Conditions

- **UNDER** on `ema1` (other=ema2)

---

### RANGE_BARS

**File:** `range_bars.yaml`  
**Complexity:** SIMPLE  
**Description:** Range bars strategy using ATR-based volatility breakouts

#### Indicators

| ID | Type | Input | Parameters |
|----|------|-------|------------|
| close | CLOSE | N/A |  |
| atr | ATR | N/A | period=14 |
| upperRange | BOLLINGER_UPPER | close | multiplier=${rangeSize}, period=20 |
| lowerRange | BOLLINGER_LOWER | close | multiplier=${rangeSize}, period=20 |

#### Entry Conditions

- **CROSSED_UP** on `close` (crosses=upperRange)

#### Exit Conditions

- **CROSSED_DOWN** on `close` (crosses=lowerRange)

#### Parameters

| Name | Type | Min | Max | Default |
|------|------|-----|-----|---------|
| rangeSize | DOUBLE | 1.0 | 3.0 | 2.0 |

---

### REGRESSION_CHANNEL

**File:** `regression_channel.yaml`  
**Complexity:** SIMPLE  
**Description:** Regression channel mean reversion strategy using Bollinger Bands as channel proxy

#### Indicators

| ID | Type | Input | Parameters |
|----|------|-------|------------|
| close | CLOSE | N/A |  |
| middle | BOLLINGER_MIDDLE | close | period=${period} |
| upper | BOLLINGER_UPPER | close | multiplier=2.0, period=${period} |
| lower | BOLLINGER_LOWER | close | multiplier=2.0, period=${period} |

#### Entry Conditions

- **CROSSED_UP** on `close` (crosses=lower)

#### Exit Conditions

- **CROSSED_DOWN** on `close` (crosses=upper)

#### Parameters

| Name | Type | Min | Max | Default |
|------|------|-----|-----|---------|
| period | INTEGER | 15 | 50 | 20 |

---

### RENKO_CHART

**File:** `renko_chart.yaml`  
**Complexity:** SIMPLE  
**Description:** Renko chart style strategy using ATR-based volatility breakouts for trend following

#### Indicators

| ID | Type | Input | Parameters |
|----|------|-------|------------|
| close | CLOSE | N/A |  |
| atr | ATR | N/A | period=14 |
| ema | EMA | close | period=20 |

#### Entry Conditions

- **CROSSED_UP** on `close` (crosses=ema)
- **IS_RISING** on `close` (barCount=2)

#### Exit Conditions

- **CROSSED_DOWN** on `close` (crosses=ema)

#### Parameters

| Name | Type | Min | Max | Default |
|------|------|-----|-----|---------|
| brickSize | DOUBLE | 0.5 | 3.0 | 1.0 |

---

### ROC_MA_CROSSOVER

**File:** `roc_ma_crossover.yaml`  
**Complexity:** SIMPLE  
**Description:** Rate of Change crosses its Moving Average

#### Indicators

| ID | Type | Input | Parameters |
|----|------|-------|------------|
| roc | ROC | close | period=${rocPeriod} |
| rocMa | SMA | roc | period=${maPeriod} |

#### Entry Conditions

- **CROSSED_UP** on `roc` (crosses=rocMa)

#### Exit Conditions

- **CROSSED_DOWN** on `roc` (crosses=rocMa)

#### Parameters

| Name | Type | Min | Max | Default |
|------|------|-----|-----|---------|
| rocPeriod | INTEGER | 5 | 20 | 10 |
| maPeriod | INTEGER | 5 | 30 | 14 |

---

### RSI_EMA_CROSSOVER

**File:** `rsi_ema_crossover.yaml`  
**Complexity:** SIMPLE  
**Description:** RSI crosses its EMA with overbought/oversold filters

#### Indicators

| ID | Type | Input | Parameters |
|----|------|-------|------------|
| rsi | RSI | close | period=${rsiPeriod} |
| rsiEma | EMA | rsi | period=${emaPeriod} |
| overboughtLevel | CONSTANT | N/A | value=70 |
| oversoldLevel | CONSTANT | N/A | value=30 |

#### Entry Conditions

- **CROSSED_UP** on `rsi` (crosses=rsiEma)
- **UNDER** on `rsi` (value=70)

#### Exit Conditions

- **CROSSED_DOWN** on `rsi` (crosses=rsiEma)
- **OVER** on `rsi` (value=30)

#### Parameters

| Name | Type | Min | Max | Default |
|------|------|-----|-----|---------|
| rsiPeriod | INTEGER | 7 | 21 | 14 |
| emaPeriod | INTEGER | 5 | 20 | 10 |

---

### RVI

**File:** `rvi.yaml`  
**Complexity:** SIMPLE  
**Description:** Relative Vigor Index strategy using RSI as vigor proxy with signal line crossover

#### Indicators

| ID | Type | Input | Parameters |
|----|------|-------|------------|
| close | CLOSE | N/A |  |
| rvi | RSI | close | period=${period} |
| rviSignal | SMA | rvi | period=4 |

#### Entry Conditions

- **CROSSED_UP** on `rvi` (crosses=rviSignal)

#### Exit Conditions

- **CROSSED_DOWN** on `rvi` (crosses=rviSignal)

#### Parameters

| Name | Type | Min | Max | Default |
|------|------|-----|-----|---------|
| period | INTEGER | 7 | 21 | 10 |

---

### SAR_MFI

**File:** `sar_mfi.yaml`  
**Complexity:** MEDIUM  
**Description:** Parabolic SAR combined with Money Flow Index for trend confirmation with volume

#### Indicators

| ID | Type | Input | Parameters |
|----|------|-------|------------|
| close | CLOSE | N/A |  |
| sar | PARABOLIC_SAR | N/A |  |
| mfi | MFI | N/A | period=${mfiPeriod} |

#### Entry Conditions

- **CROSSED_UP** on `close` (crosses=sar)
- **UNDER** on `mfi` (value=30)

#### Exit Conditions

- **CROSSED_DOWN** on `close` (crosses=sar)
- **OVER** on `mfi` (value=70)

#### Parameters

| Name | Type | Min | Max | Default |
|------|------|-----|-----|---------|
| accelerationFactorStart | DOUBLE | 0.01 | 0.03 | 0.02 |
| accelerationFactorIncrement | DOUBLE | 0.01 | 0.03 | 0.02 |
| accelerationFactorMax | DOUBLE | 0.15 | 0.25 | 0.2 |
| mfiPeriod | INTEGER | 10 | 20 | 14 |

---

### SMA_EMA_CROSSOVER

**File:** `sma_ema_crossover.yaml`  
**Complexity:** SIMPLE  
**Description:** Simple Moving Average crosses Exponential Moving Average

#### Indicators

| ID | Type | Input | Parameters |
|----|------|-------|------------|
| sma | SMA | close | period=${smaPeriod} |
| ema | EMA | close | period=${emaPeriod} |

#### Entry Conditions

- **CROSSED_UP** on `sma` (crosses=ema)

#### Exit Conditions

- **CROSSED_DOWN** on `sma` (crosses=ema)

#### Parameters

| Name | Type | Min | Max | Default |
|------|------|-----|-----|---------|
| smaPeriod | INTEGER | 5 | 50 | 20 |
| emaPeriod | INTEGER | 5 | 50 | 50 |

---

### SMA_RSI

**File:** `sma_rsi.yaml`  
**Complexity:** SIMPLE  
**Description:** SMA trend filter combined with RSI overbought/oversold signals

#### Indicators

| ID | Type | Input | Parameters |
|----|------|-------|------------|
| close | CLOSE | N/A |  |
| sma | SMA | close | period=${movingAveragePeriod} |
| rsi | RSI | close | period=${rsiPeriod} |

#### Entry Conditions

- **OVER** on `close` (other=sma)
- **UNDER** on `rsi` (value=${oversoldThreshold})

#### Exit Conditions

- **OVER** on `rsi` (value=${overboughtThreshold})

#### Parameters

| Name | Type | Min | Max | Default |
|------|------|-----|-----|---------|
| movingAveragePeriod | INTEGER | 10 | 50 | 20 |
| rsiPeriod | INTEGER | 7 | 21 | 14 |
| overboughtThreshold | DOUBLE | 70.0 | 85.0 | 70.0 |
| oversoldThreshold | DOUBLE | 15.0 | 30.0 | 30.0 |

---

### STOCHASTIC_EMA

**File:** `stochastic_ema.yaml`  
**Complexity:** MEDIUM  
**Description:** Stochastic oscillator with EMA trend filter for momentum trading

#### Indicators

| ID | Type | Input | Parameters |
|----|------|-------|------------|
| close | CLOSE | N/A |  |
| ema | EMA | close | period=${emaPeriod} |
| stochK | STOCHASTIC_K | N/A | period=${stochasticKPeriod} |

#### Entry Conditions

- **OVER** on `close` (other=ema)
- **UNDER** on `stochK` (value=${oversoldThreshold})

#### Exit Conditions

- **OVER** on `stochK` (value=${overboughtThreshold})

#### Parameters

| Name | Type | Min | Max | Default |
|------|------|-----|-----|---------|
| emaPeriod | INTEGER | 10 | 30 | 20 |
| stochasticKPeriod | INTEGER | 10 | 20 | 14 |
| stochasticDPeriod | INTEGER | 3 | 5 | 3 |
| overboughtThreshold | INTEGER | 75 | 90 | 80 |
| oversoldThreshold | INTEGER | 10 | 25 | 20 |

---

### STOCHASTIC_RSI

**File:** `stochastic_rsi.yaml`  
**Complexity:** MEDIUM  
**Description:** Stochastic RSI - enters when oversold, exits when overbought

#### Indicators

| ID | Type | Input | Parameters |
|----|------|-------|------------|
| rsi | RSI | N/A | period=${rsiPeriod} |
| stochasticK | STOCHASTIC_K | N/A | period=${stochasticKPeriod} |

#### Entry Conditions

- **OVER_CONSTANT** on `stochasticK` (threshold=${oversoldThreshold})

#### Exit Conditions

- **UNDER_CONSTANT** on `stochasticK` (threshold=${overboughtThreshold})

#### Parameters

| Name | Type | Min | Max | Default |
|------|------|-----|-----|---------|
| rsiPeriod | INTEGER | 7 | 21 | 14 |
| stochasticKPeriod | INTEGER | 7 | 21 | 14 |
| stochasticDPeriod | INTEGER | 2 | 5 | 3 |
| overboughtThreshold | INTEGER | 70 | 90 | 80 |
| oversoldThreshold | INTEGER | 10 | 30 | 20 |

---

### TICK_VOLUME_ANALYSIS

**File:** `tick_volume_analysis.yaml`  
**Complexity:** SIMPLE  
**Description:** Tick volume analysis strategy using volume indicators with EMA crossover

#### Indicators

| ID | Type | Input | Parameters |
|----|------|-------|------------|
| volume | VOLUME | N/A |  |
| volumeEma | EMA | volume | period=${tickPeriod} |
| close | CLOSE | N/A |  |
| priceEma | EMA | close | period=${tickPeriod} |

#### Entry Conditions

- **OVER** on `volume` (other=volumeEma)
- **CROSSED_UP** on `close` (crosses=priceEma)

#### Exit Conditions

- **CROSSED_DOWN** on `close` (crosses=priceEma)

#### Parameters

| Name | Type | Min | Max | Default |
|------|------|-----|-----|---------|
| tickPeriod | INTEGER | 10 | 30 | 20 |

---

### TRIPLE_EMA_CROSSOVER

**File:** `triple_ema_crossover.yaml`  
**Complexity:** MEDIUM  
**Description:** Triple EMA crossover strategy using short, medium, and long periods

#### Indicators

| ID | Type | Input | Parameters |
|----|------|-------|------------|
| shortEma | EMA | close | period=${shortEmaPeriod} |
| mediumEma | EMA | close | period=${mediumEmaPeriod} |
| longEma | EMA | close | period=${longEmaPeriod} |

#### Entry Conditions

- **ABOVE** on `shortEma` (other=mediumEma)
- **ABOVE** on `mediumEma` (other=longEma)

#### Exit Conditions

- **BELOW** on `shortEma` (other=mediumEma)
- **BELOW** on `mediumEma` (other=longEma)

#### Parameters

| Name | Type | Min | Max | Default |
|------|------|-----|-----|---------|
| shortEmaPeriod | INTEGER | 5 | 15 | 8 |
| mediumEmaPeriod | INTEGER | 10 | 30 | 21 |
| longEmaPeriod | INTEGER | 30 | 60 | 55 |

---

### TRIX_SIGNAL_LINE

**File:** `trix_signal_line.yaml`  
**Complexity:** SIMPLE  
**Description:** TRIX with signal line crossover - enters when TRIX crosses above its SMA signal line

#### Indicators

| ID | Type | Input | Parameters |
|----|------|-------|------------|
| trix | TRIX | N/A | period=${trixPeriod} |
| signalLine | SMA | trix | period=${signalPeriod} |

#### Entry Conditions

- **CROSSED_UP** on `trix` (crosses=signalLine)

#### Exit Conditions

- **CROSSED_DOWN** on `trix` (crosses=signalLine)

#### Parameters

| Name | Type | Min | Max | Default |
|------|------|-----|-----|---------|
| trixPeriod | INTEGER | 5 | 50 | 15 |
| signalPeriod | INTEGER | 3 | 20 | 9 |

---

### VARIABLE_PERIOD_EMA

**File:** `variable_period_ema.yaml`  
**Complexity:** MEDIUM  
**Description:** Variable period EMA strategy using KAMA for adaptive moving average crossover

#### Indicators

| ID | Type | Input | Parameters |
|----|------|-------|------------|
| close | CLOSE | N/A |  |
| fastKama | KAMA | close | fastPeriod=2, period=${minPeriod}, slowPeriod=30 |
| slowKama | KAMA | close | fastPeriod=2, period=${maxPeriod}, slowPeriod=30 |

#### Entry Conditions

- **CROSSED_UP** on `fastKama` (crosses=slowKama)

#### Exit Conditions

- **CROSSED_DOWN** on `fastKama` (crosses=slowKama)

#### Parameters

| Name | Type | Min | Max | Default |
|------|------|-----|-----|---------|
| minPeriod | INTEGER | 5 | 15 | 10 |
| maxPeriod | INTEGER | 20 | 50 | 30 |

---

### VOLATILITY_STOP

**File:** `volatility_stop.yaml`  
**Complexity:** SIMPLE  
**Description:** Volatility-based stop strategy using ATR for dynamic stop levels

#### Indicators

| ID | Type | Input | Parameters |
|----|------|-------|------------|
| close | CLOSE | N/A |  |
| atr | ATR | N/A | period=${atrPeriod} |
| ema | EMA | close | period=${atrPeriod} |

#### Entry Conditions

- **CROSSED_UP** on `close` (crosses=ema)

#### Exit Conditions

- **STOP_LOSS** on `?` (percentage=${multiplier})

#### Parameters

| Name | Type | Min | Max | Default |
|------|------|-----|-----|---------|
| atrPeriod | INTEGER | 10 | 25 | 14 |
| multiplier | DOUBLE | 1.5 | 4.0 | 2.5 |

---

### VOLUME_BREAKOUT

**File:** `volume_breakout.yaml`  
**Complexity:** SIMPLE  
**Description:** Volume breakout strategy detecting high volume moves with price confirmation

#### Indicators

| ID | Type | Input | Parameters |
|----|------|-------|------------|
| close | CLOSE | N/A |  |
| volume | VOLUME | N/A |  |
| volumeSma | SMA | volume | period=20 |
| priceSma | SMA | close | period=20 |

#### Entry Conditions

- **CROSSED_UP** on `close` (crosses=priceSma)
- **IS_RISING** on `volume` (barCount=2)

#### Exit Conditions

- **CROSSED_DOWN** on `close` (crosses=priceSma)

#### Parameters

| Name | Type | Min | Max | Default |
|------|------|-----|-----|---------|
| volumeMultiplier | DOUBLE | 1.5 | 3.0 | 2.0 |

---

### VOLUME_PROFILE

**File:** `volume_profile.yaml`  
**Complexity:** SIMPLE  
**Description:** Volume profile strategy using OBV with EMA for volume-weighted trend detection

#### Indicators

| ID | Type | Input | Parameters |
|----|------|-------|------------|
| obv | OBV | N/A |  |
| obvEma | EMA | obv | period=${period} |
| close | CLOSE | N/A |  |
| priceEma | EMA | close | period=${period} |

#### Entry Conditions

- **CROSSED_UP** on `obv` (crosses=obvEma)
- **OVER** on `close` (other=priceEma)

#### Exit Conditions

- **CROSSED_DOWN** on `obv` (crosses=obvEma)

#### Parameters

| Name | Type | Min | Max | Default |
|------|------|-----|-----|---------|
| period | INTEGER | 10 | 30 | 20 |

---

### VOLUME_PROFILE_DEVIATIONS

**File:** `volume_profile_deviations.yaml`  
**Complexity:** MEDIUM  
**Description:** Volume profile with standard deviation bands for mean reversion trading

#### Indicators

| ID | Type | Input | Parameters |
|----|------|-------|------------|
| close | CLOSE | N/A |  |
| volume | VOLUME | N/A |  |
| volumeSma | SMA | volume | period=${period} |
| upperBand | BOLLINGER_UPPER | close | multiplier=2.0, period=${period} |
| lowerBand | BOLLINGER_LOWER | close | multiplier=2.0, period=${period} |

#### Entry Conditions

- **CROSSED_UP** on `close` (crosses=lowerBand)
- **OVER** on `volume` (other=volumeSma)

#### Exit Conditions

- **CROSSED_DOWN** on `close` (crosses=upperBand)

#### Parameters

| Name | Type | Min | Max | Default |
|------|------|-----|-----|---------|
| period | INTEGER | 15 | 40 | 20 |

---

### VOLUME_SPREAD_ANALYSIS

**File:** `volume_spread_analysis.yaml`  
**Complexity:** SIMPLE  
**Description:** Volume spread analysis strategy comparing price spread with volume for trend confirmation

#### Indicators

| ID | Type | Input | Parameters |
|----|------|-------|------------|
| close | CLOSE | N/A |  |
| volume | VOLUME | N/A |  |
| volumeEma | EMA | volume | period=${volumePeriod} |
| priceEma | EMA | close | period=${volumePeriod} |

#### Entry Conditions

- **CROSSED_UP** on `close` (crosses=priceEma)
- **OVER** on `volume` (other=volumeEma)

#### Exit Conditions

- **CROSSED_DOWN** on `close` (crosses=priceEma)

#### Parameters

| Name | Type | Min | Max | Default |
|------|------|-----|-----|---------|
| volumePeriod | INTEGER | 10 | 30 | 20 |

---

### VOLUME_WEIGHTED_MACD

**File:** `volume_weighted_macd.yaml`  
**Complexity:** MODERATE  
**Description:** Volume Weighted MACD - enters when MACD line crosses above signal line, exits when it crosses below

#### Indicators

| ID | Type | Input | Parameters |
|----|------|-------|------------|
| macdLine | VOLUME_WEIGHTED_MACD | N/A | longPeriod=${longPeriod}, shortPeriod=${shortPeriod} |
| signalLine | EMA | N/A | period=${signalPeriod}, source=macdLine |

#### Entry Conditions

- **CROSSED_UP** on `macdLine` (crosses=signalLine)

#### Exit Conditions

- **CROSSED_DOWN** on `macdLine` (crosses=signalLine)

#### Parameters

| Name | Type | Min | Max | Default |
|------|------|-----|-----|---------|
| shortPeriod | INTEGER | 5 | 20 | 12 |
| longPeriod | INTEGER | 15 | 50 | 26 |
| signalPeriod | INTEGER | 5 | 15 | 9 |

---

### VPT

**File:** `vpt.yaml`  
**Complexity:** SIMPLE  
**Description:** Volume Price Trend strategy using NVI indicator with EMA signal crossover

#### Indicators

| ID | Type | Input | Parameters |
|----|------|-------|------------|
| nvi | NVI | N/A |  |
| nviSignal | EMA | nvi | period=${period} |

#### Entry Conditions

- **CROSSED_UP** on `nvi` (crosses=nviSignal)

#### Exit Conditions

- **CROSSED_DOWN** on `nvi` (crosses=nviSignal)

#### Parameters

| Name | Type | Min | Max | Default |
|------|------|-----|-----|---------|
| period | INTEGER | 10 | 30 | 20 |

---

### VWAP_CROSSOVER

**File:** `vwap_crossover.yaml`  
**Complexity:** SIMPLE  
**Description:** VWAP crossover strategy using price crossing VWAP for intraday trading

#### Indicators

| ID | Type | Input | Parameters |
|----|------|-------|------------|
| close | CLOSE | N/A |  |
| vwap | VWAP | N/A | period=${vwapPeriod} |
| priceMa | SMA | close | period=${movingAveragePeriod} |

#### Entry Conditions

- **CROSSED_UP** on `close` (crosses=vwap)

#### Exit Conditions

- **CROSSED_DOWN** on `close` (crosses=vwap)

#### Parameters

| Name | Type | Min | Max | Default |
|------|------|-----|-----|---------|
| vwapPeriod | INTEGER | 10 | 30 | 20 |
| movingAveragePeriod | INTEGER | 5 | 20 | 10 |

---

### VWAP_MEAN_REVERSION

**File:** `vwap_mean_reversion.yaml`  
**Complexity:** MEDIUM  
**Description:** VWAP mean reversion strategy buying below VWAP and selling above for range trading

#### Indicators

| ID | Type | Input | Parameters |
|----|------|-------|------------|
| close | CLOSE | N/A |  |
| vwap | VWAP | N/A | period=${vwapPeriod} |
| upperBand | BOLLINGER_UPPER | close | multiplier=${deviationMultiplier}, period=${movingAveragePeriod} |
| lowerBand | BOLLINGER_LOWER | close | multiplier=${deviationMultiplier}, period=${movingAveragePeriod} |

#### Entry Conditions

- **UNDER** on `close` (other=vwap)
- **CROSSED_UP** on `close` (crosses=lowerBand)

#### Exit Conditions

- **OVER** on `close` (other=vwap)
- **CROSSED_DOWN** on `close` (crosses=upperBand)

#### Parameters

| Name | Type | Min | Max | Default |
|------|------|-----|-----|---------|
| vwapPeriod | INTEGER | 10 | 30 | 20 |
| movingAveragePeriod | INTEGER | 15 | 30 | 20 |
| deviationMultiplier | DOUBLE | 1.5 | 3.0 | 2.0 |

---
