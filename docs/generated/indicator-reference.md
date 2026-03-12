# Indicator Reference

Auto-generated from strategy YAML configs.

**Total unique indicator types: 53**

| Indicator | Used In # Strategies | Parameters |
|-----------|---------------------|------------|
| ADX | 2 | period |
| AROON_DOWN | 1 | period |
| AROON_UP | 1 | period |
| ATR | 5 | period |
| AWESOME_OSCILLATOR | 1 | longPeriod, shortPeriod |
| BOLLINGER_LOWER | 5 | k, multiplier, period |
| BOLLINGER_MIDDLE | 1 | period |
| BOLLINGER_UPPER | 5 | k, multiplier, period |
| CCI | 1 | period |
| CHAIKIN_OSCILLATOR | 1 | longPeriod, shortPeriod |
| CLOSE | 27 | none |
| CLOSE_PRICE | 1 | none |
| CMF | 1 | period |
| CMO | 1 | period |
| CONSTANT | 3 | value |
| DEMA | 1 | period |
| DONCHIAN_LOWER | 4 | period |
| DONCHIAN_MIDDLE | 1 | period |
| DONCHIAN_UPPER | 4 | period |
| DPO | 1 | period |
| EMA | 33 | period, source |
| FRAMA | 1 | alpha, fc, sc |
| HEIKEN_ASHI_CLOSE | 1 | period |
| HEIKEN_ASHI_OPEN | 1 | period |
| HIGH | 1 | none |
| KAMA | 2 | fastPeriod, period, slowPeriod |
| KLINGER_VOLUME_OSCILLATOR | 1 | longPeriod, shortPeriod |
| LINEAR_REGRESSION_LOWER_CHANNEL | 1 | multiplier, period |
| LINEAR_REGRESSION_UPPER_CHANNEL | 1 | multiplier, period |
| LOW | 1 | none |
| MACD | 2 | longPeriod, shortPeriod |
| MASS_INDEX | 1 | emaPeriod, sumPeriod |
| MFI | 3 | period |
| MINUS_DI | 1 | period |
| MOMENTUM | 2 | period |
| NVI | 1 | none |
| OBV | 2 | none |
| PARABOLIC_SAR | 2 | none |
| PLUS_DI | 1 | period |
| PREVIOUS | 2 | n |
| PRICE_OSCILLATOR | 1 | fastPeriod, slowPeriod |
| PVT | 1 | none |
| ROC | 6 | period |
| RSI | 4 | period |
| SMA | 12 | period |
| STOCHASTIC_K | 3 | period |
| TEMA | 1 | period |
| TRIX | 1 | period |
| TYPICAL_PRICE | 1 | none |
| VOLUME | 4 | none |
| VOLUME_WEIGHTED_MACD | 1 | longPeriod, shortPeriod |
| VWAP | 2 | period |
| WILLIAMS_R | 1 | period |

## Details

### ADX

Used in **2** strategies:

- ADX_DMI
- ADX_STOCHASTIC

### AROON_DOWN

Used in **1** strategies:

- AROON_MFI

### AROON_UP

Used in **1** strategies:

- AROON_MFI

### ATR

Used in **5** strategies:

- ATR_CCI
- ATR_TRAILING_STOP
- RANGE_BARS
- RENKO_CHART
- VOLATILITY_STOP

### AWESOME_OSCILLATOR

Used in **1** strategies:

- AWESOME_OSCILLATOR

### BOLLINGER_LOWER

Used in **5** strategies:

- BBAND_WILLIAMS_R
- RANGE_BARS
- REGRESSION_CHANNEL
- VOLUME_PROFILE_DEVIATIONS
- VWAP_MEAN_REVERSION

### BOLLINGER_MIDDLE

Used in **1** strategies:

- REGRESSION_CHANNEL

### BOLLINGER_UPPER

Used in **5** strategies:

- BBAND_WILLIAMS_R
- RANGE_BARS
- REGRESSION_CHANNEL
- VOLUME_PROFILE_DEVIATIONS
- VWAP_MEAN_REVERSION

### CCI

Used in **1** strategies:

- ATR_CCI

### CHAIKIN_OSCILLATOR

Used in **1** strategies:

- CHAIKIN_OSCILLATOR

### CLOSE

Used in **27** strategies:

- ATR_TRAILING_STOP
- DONCHIAN_BREAKOUT
- DOUBLE_TOP_BOTTOM
- FIBONACCI_RETRACEMENTS
- GANN_SWING
- ICHIMOKU_CLOUD
- KST_OSCILLATOR
- PARABOLIC_SAR
- PIVOT
- PRICE_GAP
- RAINBOW_OSCILLATOR
- RANGE_BARS
- REGRESSION_CHANNEL
- RENKO_CHART
- RVI
- SAR_MFI
- SMA_RSI
- STOCHASTIC_EMA
- TICK_VOLUME_ANALYSIS
- VARIABLE_PERIOD_EMA
- VOLATILITY_STOP
- VOLUME_BREAKOUT
- VOLUME_PROFILE
- VOLUME_PROFILE_DEVIATIONS
- VOLUME_SPREAD_ANALYSIS
- VWAP_CROSSOVER
- VWAP_MEAN_REVERSION

### CLOSE_PRICE

Used in **1** strategies:

- BBAND_WILLIAMS_R

### CMF

Used in **1** strategies:

- CMF_ZERO_LINE

### CMO

Used in **1** strategies:

- CMO_MFI

### CONSTANT

Used in **3** strategies:

- CHAIKIN_OSCILLATOR
- RSI_EMA_CROSSOVER

### DEMA

Used in **1** strategies:

- DEMA_TEMA_CROSSOVER

### DONCHIAN_LOWER

Used in **4** strategies:

- DONCHIAN_BREAKOUT
- FIBONACCI_RETRACEMENTS
- GANN_SWING
- PIVOT

### DONCHIAN_MIDDLE

Used in **1** strategies:

- FIBONACCI_RETRACEMENTS

### DONCHIAN_UPPER

Used in **4** strategies:

- DONCHIAN_BREAKOUT
- FIBONACCI_RETRACEMENTS
- GANN_SWING
- PIVOT

### DPO

Used in **1** strategies:

- DPO_CROSSOVER

### EMA

Used in **33** strategies:

- DOUBLE_EMA_CROSSOVER
- DOUBLE_TOP_BOTTOM
- ELDER_RAY_MA
- EMA_MACD
- ICHIMOKU_CLOUD
- KLINGER_VOLUME
- MACD_CROSSOVER
- OBV_EMA
- PRICE_GAP
- PRICE_OSCILLATOR_SIGNAL
- PVT
- RAINBOW_OSCILLATOR
- RENKO_CHART
- RSI_EMA_CROSSOVER
- SMA_EMA_CROSSOVER
- STOCHASTIC_EMA
- TICK_VOLUME_ANALYSIS
- TRIPLE_EMA_CROSSOVER
- VOLATILITY_STOP
- VOLUME_PROFILE
- VOLUME_SPREAD_ANALYSIS
- VOLUME_WEIGHTED_MACD
- VPT

### FRAMA

Used in **1** strategies:

- FRAMA

### HEIKEN_ASHI_CLOSE

Used in **1** strategies:

- HEIKEN_ASHI

### HEIKEN_ASHI_OPEN

Used in **1** strategies:

- HEIKEN_ASHI

### HIGH

Used in **1** strategies:

- ELDER_RAY_MA

### KAMA

Used in **2** strategies:

- VARIABLE_PERIOD_EMA

### KLINGER_VOLUME_OSCILLATOR

Used in **1** strategies:

- KLINGER_VOLUME

### LINEAR_REGRESSION_LOWER_CHANNEL

Used in **1** strategies:

- LINEAR_REGRESSION_CHANNELS

### LINEAR_REGRESSION_UPPER_CHANNEL

Used in **1** strategies:

- LINEAR_REGRESSION_CHANNELS

### LOW

Used in **1** strategies:

- ELDER_RAY_MA

### MACD

Used in **2** strategies:

- EMA_MACD
- MACD_CROSSOVER

### MASS_INDEX

Used in **1** strategies:

- MASS_INDEX

### MFI

Used in **3** strategies:

- AROON_MFI
- CMO_MFI
- SAR_MFI

### MINUS_DI

Used in **1** strategies:

- ADX_DMI

### MOMENTUM

Used in **2** strategies:

- MOMENTUM_PINBALL

### NVI

Used in **1** strategies:

- VPT

### OBV

Used in **2** strategies:

- OBV_EMA
- VOLUME_PROFILE

### PARABOLIC_SAR

Used in **2** strategies:

- PARABOLIC_SAR
- SAR_MFI

### PLUS_DI

Used in **1** strategies:

- ADX_DMI

### PREVIOUS

Used in **2** strategies:

- ATR_CCI
- ATR_TRAILING_STOP

### PRICE_OSCILLATOR

Used in **1** strategies:

- PRICE_OSCILLATOR_SIGNAL

### PVT

Used in **1** strategies:

- PVT

### ROC

Used in **6** strategies:

- KST_OSCILLATOR
- MOMENTUM_SMA_CROSSOVER
- ROC_MA_CROSSOVER

### RSI

Used in **4** strategies:

- RSI_EMA_CROSSOVER
- RVI
- SMA_RSI
- STOCHASTIC_RSI

### SMA

Used in **12** strategies:

- DPO_CROSSOVER
- KST_OSCILLATOR
- MOMENTUM_SMA_CROSSOVER
- ROC_MA_CROSSOVER
- RVI
- SMA_EMA_CROSSOVER
- SMA_RSI
- TRIX_SIGNAL_LINE
- VOLUME_BREAKOUT
- VOLUME_PROFILE_DEVIATIONS
- VWAP_CROSSOVER

### STOCHASTIC_K

Used in **3** strategies:

- ADX_STOCHASTIC
- STOCHASTIC_EMA
- STOCHASTIC_RSI

### TEMA

Used in **1** strategies:

- DEMA_TEMA_CROSSOVER

### TRIX

Used in **1** strategies:

- TRIX_SIGNAL_LINE

### TYPICAL_PRICE

Used in **1** strategies:

- PIVOT

### VOLUME

Used in **4** strategies:

- TICK_VOLUME_ANALYSIS
- VOLUME_BREAKOUT
- VOLUME_PROFILE_DEVIATIONS
- VOLUME_SPREAD_ANALYSIS

### VOLUME_WEIGHTED_MACD

Used in **1** strategies:

- VOLUME_WEIGHTED_MACD

### VWAP

Used in **2** strategies:

- VWAP_CROSSOVER
- VWAP_MEAN_REVERSION

### WILLIAMS_R

Used in **1** strategies:

- BBAND_WILLIAMS_R
