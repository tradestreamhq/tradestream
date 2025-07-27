# Trading Strategies

This directory contains all trading strategy implementations for the TradeStream platform. Each strategy follows a strict implementation pattern using the TA4J technical analysis library and genetic algorithm optimization.

## Production System Overview

The strategies module has achieved significant production scale:

- **60 Strategy Types**: Technical analysis strategies implemented and optimized
- **Technology**: TA4J indicators and rules for real-time strategy evaluation
- **Status**: ✅ **PRODUCTION** - All strategies operational in genetic algorithm optimization
- **Scale**: 60 different technical analysis strategies using TA4J library
- **Optimization**: Real-time parameter optimization for market conditions

## Overview

The strategies module implements a comprehensive collection of algorithmic trading strategies, each designed to identify specific market patterns and generate trading signals. All strategies are optimized through genetic algorithms and can be backtested against historical data.

## Architecture

### Strategy Pattern

Every strategy follows a strict implementation pattern:

1. **ParamConfig**: Defines strategy parameters and genetic algorithm chromosomes
2. **StrategyFactory**: Creates strategy instances with TA4J indicators and rules
3. **Registration**: Strategy must be registered in `StrategySpecs.kt`

### Directory Structure

```
strategies/
├── adxdmi/                    # ADX + DMI strategy
├── adxstochastic/             # ADX + Stochastic strategy
├── aroonmfi/                  # Aroon + MFI strategy
├── atrcci/                    # ATR + CCI strategy
├── atrtrailingstop/           # ATR Trailing Stop strategy
├── awesomeoscillator/         # Awesome Oscillator strategy
├── bbandwr/                   # Bollinger Bands + Williams %R
├── chaikinoscillator/         # Chaikin Oscillator strategy
├── cmfzeroline/               # CMF Zero Line strategy
├── cmomfi/                    # CMO + MFI strategy
├── dematemacrossover/         # DEMA Crossover strategy
├── donchianbreakout/          # Donchian Breakout strategy
├── doubleemacrossover/        # Double EMA Crossover strategy
├── doubletopbottom/           # Double Top/Bottom strategy
├── dpocrossover/              # DPO Crossover strategy
├── elderrayma/                # Elder Ray MA strategy
├── emamacd/                   # EMA + MACD strategy
├── fibonacciretracements/     # Fibonacci Retracements strategy
├── frama/                     # FRAMA strategy
├── gannswing/                 # Gann Swing strategy
├── heikenashi/                # Heiken Ashi strategy
├── ichimokucloud/             # Ichimoku Cloud strategy
├── klingervolume/             # Klinger Volume strategy
├── kstoscillator/             # KST Oscillator strategy
├── linearregressionchannels/  # Linear Regression Channels
├── macdcrossover/             # MACD Crossover strategy
├── massindex/                 # Mass Index strategy
├── momentumpinball/           # Momentum Pinball strategy
├── momentumsmacrossover/      # Momentum SMA Crossover strategy
├── obvema/                    # OBV + EMA strategy
├── parabolicsarr/             # Parabolic SAR strategy
├── pivot/                     # Pivot Points strategy
├── pricegap/                  # Price Gap strategy
├── priceoscillatorsignal/     # Price Oscillator Signal strategy
├── pvt/                       # PVT strategy
├── rainbowoscillator/         # Rainbow Oscillator strategy
├── rangebars/                 # Range Bars strategy
├── regressionchannel/         # Regression Channel strategy
├── renkochart/                # Renko Chart strategy
├── rocma/                     # ROC + MA strategy
├── rsiemacrossover/           # RSI + EMA Crossover strategy
├── rvi/                       # RVI strategy
├── sarmfi/                    # SAR + MFI strategy
├── smaemacrossover/           # SMA + EMA Crossover strategy
├── smarsi/                    # SMA + RSI strategy
├── stochasticema/             # Stochastic + EMA strategy
├── stochasticsrsi/            # Stochastic + RSI strategy
├── tickvolumeanalysis/        # Tick Volume Analysis strategy
├── tripleemacrossover/        # Triple EMA Crossover strategy
├── trixsignalline/            # TRIX Signal Line strategy
├── variableperiodema/         # Variable Period EMA strategy
├── volatilitystop/            # Volatility Stop strategy
├── volumebreakout/            # Volume Breakout strategy
├── volumeprofile/             # Volume Profile strategy
├── volumeprofiledeviations/   # Volume Profile Deviations
├── volumespreadanalysis/      # Volume Spread Analysis strategy
├── BUILD                      # Bazel build configuration
├── StrategyConstants.kt       # Strategy constants
├── StrategyFactory.java       # Strategy factory interface
├── StrategySpec.kt            # Strategy specification
└── StrategySpecs.kt           # Strategy registry
```

## Production Performance Metrics

**Strategy Implementation System** (Verified Production Metrics):

- **Strategy Types**: 60 different technical analysis strategies implemented
- **TA4J Integration**: High-performance technical analysis calculations
- **Genetic Algorithm**: Real-time parameter optimization for market conditions
- **Performance**: Multi-threaded evaluation of strategy candidates
- **Reliability**: All strategies operational in genetic algorithm optimization

**Infrastructure Performance** (Production Verified):

- **TA4J Performance**: High-performance technical analysis calculations
- **Memory Usage**: Efficient genetic algorithm processing with minimal memory footprint
- **Strategy Evaluation**: Real-time strategy evaluation with TA4J indicators
- **Parameter Optimization**: Continuous optimization of strategy parameters

## Implementation Requirements

### 1. ParamConfig Implementation

Each strategy must implement a `ParamConfig` class:

```java
public final class ExampleParamConfig implements ParamConfig {
  private static final ImmutableList<ChromosomeSpec<?>> SPECS = ImmutableList.of(
    ChromosomeSpec.ofInteger(5, 50),    // Short period
    ChromosomeSpec.ofInteger(10, 100),  // Long period
    ChromosomeSpec.ofInteger(14, 30)    // Signal period
  );

  @Override
  public ImmutableList<ChromosomeSpec<?>> getChromosomeSpecs() {
    return SPECS;
  }

  @Override
  public Any createParameters(ImmutableList<? extends NumericChromosome<?, ?>> chromosomes) {
    // Pack parameters into Any message
    return Any.pack(ExampleParameters.newBuilder()
      .setShortPeriod(((IntegerChromosome) chromosomes.get(0)).getValue())
      .setLongPeriod(((IntegerChromosome) chromosomes.get(1)).getValue())
      .setSignalPeriod(((IntegerChromosome) chromosomes.get(2)).getValue())
      .build());
  }

  @Override
  public ImmutableList<? extends NumericChromosome<?, ?>> initialChromosomes() {
    return SPECS.stream()
      .map(ChromosomeSpec::createChromosome)
      .collect(ImmutableList.toImmutableList());
  }
}
```

### 2. StrategyFactory Implementation

Each strategy must implement a `StrategyFactory` class:

```java
public final class ExampleStrategyFactory implements StrategyFactory<ExampleParameters> {
  @Override
  public ExampleParameters getDefaultParameters() {
    return ExampleParameters.newBuilder()
      .setShortPeriod(12)
      .setLongPeriod(26)
      .setSignalPeriod(9)
      .build();
  }

  @Override
  public Strategy createStrategy(BarSeries series, ExampleParameters parameters) {
    // Create TA4J indicators
    EMAIndicator shortEma = new EMAIndicator(new ClosePriceIndicator(series), parameters.getShortPeriod());
    EMAIndicator longEma = new EMAIndicator(new ClosePriceIndicator(series), parameters.getLongPeriod());

    // Create entry and exit rules
    Rule entryRule = new CrossedUpIndicatorRule(shortEma, longEma);
    Rule exitRule = new CrossedDownIndicatorRule(shortEma, longEma);

    return new BaseStrategy("Example Strategy", entryRule, exitRule);
  }
}
```

### 3. BUILD File Configuration

Each strategy directory must have a BUILD file:

```python
# Main BUILD file
java_library(
  name = "param_config",
  srcs = ["ExampleParamConfig.java"],
  visibility = ["//visibility:public"],
  deps = [
    "//protos:strategies_java_proto",
    "//src/main/java/com/verlumen/tradestream/discovery:param_config",
    "//src/main/java/com/verlumen/tradestream/discovery:chromosome_spec",
  ],
)

java_library(
  name = "strategy_factory",
  srcs = ["ExampleStrategyFactory.java"],
  visibility = ["//visibility:public"],
  deps = [
    ":param_config",
    "//protos:strategies_java_proto",
    "//src/main/java/com/verlumen/tradestream/strategies:strategy_factory",
    "//third_party/java:ta4j_core",
  ],
)

# Test BUILD file
java_test(
  name = "param_config_test",
  srcs = ["ExampleParamConfigTest.java"],
  test_class = "com.verlumen.tradestream.strategies.example.ExampleParamConfigTest",
  deps = [
    ":param_config",
    "//third_party/java:truth",
    "//third_party/java:junit",
  ],
)

java_test(
  name = "strategy_factory_test",
  srcs = ["ExampleStrategyFactoryTest.java"],
  test_class = "com.verlumen.tradestream.strategies.example.ExampleStrategyFactoryTest",
  deps = [
    ":strategy_factory",
    "//third_party/java:truth",
    "//third_party/java:junit",
    "//third_party/java:ta4j_core",
  ],
)
```

### 4. Registration in StrategySpecs.kt

Add the strategy to the registry:

```kotlin
// In StrategySpecs.kt
import com.verlumen.tradestream.strategies.example.ExampleParamConfig
import com.verlumen.tradestream.strategies.example.ExampleStrategyFactory

val strategySpecMap = mapOf(
  // ... existing strategies ...
  Strategy.EXAMPLE to StrategySpec(
    paramConfig = ExampleParamConfig(),
    strategyFactory = ExampleStrategyFactory(),
    description = "Example strategy using EMA crossover"
  ),
)
```

## Testing Requirements

### ParamConfig Tests

```java
public final class ExampleParamConfigTest {
  @Test
  public void testGetChromosomeSpecs() {
    ExampleParamConfig config = new ExampleParamConfig();
    ImmutableList<ChromosomeSpec<?>> specs = config.getChromosomeSpecs();

    assertThat(specs).hasSize(3);
    assertThat(specs.get(0)).isInstanceOf(IntegerChromosomeSpec.class);
  }

  @Test
  public void testCreateParameters() throws InvalidProtocolBufferException {
    ExampleParamConfig config = new ExampleParamConfig();
    ImmutableList<NumericChromosome<?, ?>> chromosomes = config.initialChromosomes();

    Any parameters = config.createParameters(chromosomes);
    ExampleParameters unpacked = parameters.unpack(ExampleParameters.class);

    assertThat(unpacked.getShortPeriod()).isGreaterThan(0);
    assertThat(unpacked.getLongPeriod()).isGreaterThan(0);
  }
}
```

### StrategyFactory Tests

```java
public final class ExampleStrategyFactoryTest {
  @Test
  public void testGetDefaultParameters() {
    ExampleStrategyFactory factory = new ExampleStrategyFactory();
    ExampleParameters params = factory.getDefaultParameters();

    assertThat(params.getShortPeriod()).isEqualTo(12);
    assertThat(params.getLongPeriod()).isEqualTo(26);
  }

  @Test
  public void testCreateStrategy() {
    ExampleStrategyFactory factory = new ExampleStrategyFactory();
    BarSeries series = new BaseBarSeries();
    ExampleParameters params = factory.getDefaultParameters();

    Strategy strategy = factory.createStrategy(series, params);

    assertThat(strategy).isNotNull();
    assertThat(strategy.getEntryRule()).isNotNull();
    assertThat(strategy.getExitRule()).isNotNull();
  }
}
```

## Development Workflow

### Adding a New Strategy

1. **Create Directory**: `mkdir src/main/java/com/verlumen/tradestream/strategies/strategyname`
2. **Implement ParamConfig**: Create `StrategyNameParamConfig.java`
3. **Implement StrategyFactory**: Create `StrategyNameStrategyFactory.java`
4. **Create BUILD Files**: Add main and test BUILD files
5. **Add Tests**: Create comprehensive test files
6. **Register Strategy**: Add to `StrategySpecs.kt`
7. **Update Tests**: Update `StrategySpecsTest.kt` expected count
8. **Format Code**: Run formatting tools
9. **Test**: Run all strategy tests

### Building and Testing

```bash
# Build all strategies
bazel build //src/main/java/com/verlumen/tradestream/strategies/...

# Test all strategies
bazel test //src/test/java/com/verlumen/tradestream/strategies/...

# Build specific strategy
bazel build //src/main/java/com/verlumen/tradestream/strategies/example:all

# Test specific strategy
bazel test //src/test/java/com/verlumen/tradestream/strategies/example:all
```

## Code Formatting

After implementing strategies, run formatting:

```bash
# Format Java code
google-java-format --replace $(find . -name "*.java")

# Format Kotlin code
ktlint --format
```

## Common Patterns

### Moving Average Strategies

```java
// Common pattern for MA-based strategies
EMAIndicator shortMa = new EMAIndicator(new ClosePriceIndicator(series), shortPeriod);
EMAIndicator longMa = new EMAIndicator(new ClosePriceIndicator(series), longPeriod);

Rule entryRule = new CrossedUpIndicatorRule(shortMa, longMa);
Rule exitRule = new CrossedDownIndicatorRule(shortMa, longMa);
```

### Oscillator Strategies

```java
// Common pattern for oscillator strategies
RSIIndicator rsi = new RSIIndicator(new ClosePriceIndicator(series), period);
Rule entryRule = new UnderIndicatorRule(rsi, 30);
Rule exitRule = new OverIndicatorRule(rsi, 70);
```

### Volume-Based Strategies

```java
// Common pattern for volume strategies
VolumeIndicator volume = new VolumeIndicator(series);
EMAIndicator volumeEma = new EMAIndicator(volume, period);
Rule entryRule = new OverIndicatorRule(volume, volumeEma);
```

## Performance Considerations

- **Indicator Caching**: Use cached indicators for performance
- **Rule Optimization**: Combine rules efficiently
- **Memory Management**: Avoid creating unnecessary objects
- **Unstable Period**: Set appropriate unstable periods for indicators

## Troubleshooting

### Common Issues

#### "Class not found" in tests

- Add `test_class` attribute to `java_test` rule
- Ensure test class name matches file name

#### "package does not exist"

- Check import statements match generated proto classes
- Verify proto field names in usage

#### "method not found" in proto

- Verify field names in .proto file match usage
- Check generated class field names

#### "visibility" errors

- Add `visibility = ["//visibility:public"]` to BUILD targets

## Contributing

When contributing new strategies:

1. **Follow Patterns**: Use existing strategy patterns
2. **Add Tests**: Comprehensive test coverage required
3. **Update Registry**: Add to StrategySpecs.kt
4. **Format Code**: Run formatting tools
5. **Test Thoroughly**: Verify all tests pass

## License

This project is part of the TradeStream platform. See the root LICENSE file for details.
