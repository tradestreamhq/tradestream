package com.verlumen.tradestream.strategies;

import static org.junit.Assert.*;

import com.google.common.collect.ImmutableList;
import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.testing.fieldbinder.Bind;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import com.google.protobuf.Message;
import java.util.Arrays;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import org.junit.Before;
import org.junit.Test;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBarSeries;
import org.ta4j.core.BaseStrategy;
import org.ta4j.core.rules.BooleanRule;

/** JUnit4 tests for StrategyStateImpl. */
public class StrategyStateFactoryImplTest {
  private static final BarSeries DUMMY_BAR_SERIES = new BaseBarSeries("DummyBarSeries");

  @Bind(to = StrategyManager.class)
  private FakeStrategyManager fakeStrategyManager;

  @Inject private StrategyStateFactoryImpl strategyStateFactory;

  @Before
  public void setUp() {
    fakeStrategyManager = new FakeStrategyManager();
    Guice.createInjector(BoundFieldModule.of(this)).injectMembers(this);
  }

  // --- getCurrentStrategy() tests ---

  @Test
  public void testGetCurrentStrategyCreatesNonNullStrategy() throws Exception {
    // Arrange
    StrategyState state = strategyStateFactory.create();
    // Act
    org.ta4j.core.Strategy result = state.getCurrentStrategy(DUMMY_BAR_SERIES);
    // Assert: a non-null strategy is returned.
    assertNotNull(result);
  }

  @Test
  public void testGetCurrentStrategyCreatesStrategyWithDefaultType() throws Exception {
    // Arrange & Act
    StrategyState state = strategyStateFactory.create();
    org.ta4j.core.Strategy result = state.getCurrentStrategy(DUMMY_BAR_SERIES);
    // Assert: the created strategy (our test strategy) records type SMA_RSI.
    TestStrategy ts = (TestStrategy) result;
    assertEquals(StrategyType.SMA_RSI, ts.getType());
  }

  // --- selectBestStrategy() tests ---

  @Test
  public void testSelectBestStrategyPicksRecordWithHighestScore() {
    // Arrange
    StrategyState state = strategyStateFactory.create();
    Any paramsDummy = Any.getDefaultInstance();
    state.updateRecord(StrategyType.SMA_RSI, paramsDummy, 100.0);
    // Act
    state.selectBestStrategy(DUMMY_BAR_SERIES);
    // Assert: the current strategy type is updated to SMA_RSI.
    assertEquals(StrategyType.SMA_RSI, state.getCurrentStrategyType());
  }

  @Test(expected = InvalidProtocolBufferException.class)
  public void testGetCurrentStrategyThrowsWhenStrategyCreationFails() throws Exception {
    // Arrange – force createStrategy to throw an exception.
    fakeStrategyManager.setThrowExceptionOnCreate(true);
    StrategyState state = strategyStateFactory.create();

    // Act: getCurrentStrategy should throw.
    state.getCurrentStrategy(DUMMY_BAR_SERIES);
  }

  // --- toStrategyMessage() tests ---

  @Test
  public void testToStrategyMessageReturnsCorrectType() {
    // Arrange
    Any paramsDummy = Any.getDefaultInstance();
    StrategyState state = strategyStateFactory.create();
    state.updateRecord(StrategyType.SMA_RSI, paramsDummy, 100.0);
    state.selectBestStrategy(DUMMY_BAR_SERIES);
    // Act
    // Use fully qualified name to avoid confusion with org.ta4j.core.Strategy
    com.verlumen.tradestream.strategies.Strategy protoMessage = state.toStrategyMessage();
    // Assert: the proto message type is SMA_RSI.
    assertEquals(StrategyType.SMA_RSI, protoMessage.getType());
  }

  @Test
  public void testToStrategyMessageReturnsCorrectParameters() {
    // Arrange
    Any paramsDummy = Any.getDefaultInstance();
    StrategyState state = strategyStateFactory.create();
    state.updateRecord(StrategyType.SMA_RSI, paramsDummy, 100.0);
    state.selectBestStrategy(DUMMY_BAR_SERIES);
    // Act
    // Use fully qualified name to avoid confusion with org.ta4j.core.Strategy
    com.verlumen.tradestream.strategies.Strategy protoMessage = state.toStrategyMessage();
    // Assert: the proto message parameters match the expected value.
    assertEquals(paramsDummy, protoMessage.getParameters());
  }

  // --- getters tests ---

  @Test
  public void testGetStrategyTypesReturnsAllExpectedTypes() {
    // Arrange & Act
    StrategyState state = strategyStateFactory.create();
    Iterable<StrategyType> types = state.getStrategyTypes();
    Set<StrategyType> typeSet = new HashSet<>();
    for (StrategyType type : types) {
      typeSet.add(type);
    }
    // Assert: the set equals the expected types.
    Set<StrategyType> expected = new HashSet<>(Arrays.asList(StrategyType.SMA_RSI));
    assertEquals(expected, typeSet);
  }

  @Test
  public void testGetCurrentStrategyTypeReturnsDefaultType() {
    // Arrange
    StrategyState state = strategyStateFactory.create();
    // Act
    StrategyType currentType = state.getCurrentStrategyType();
    // Assert: default is SMA_RSI.
    assertEquals(StrategyType.SMA_RSI, currentType);
  }

  // --- Supporting fake and test classes for testing ---

  /** A fake StrategyManager that simulates behavior for testing. */
  public static class FakeStrategyManager implements StrategyManager {
    private final List<StrategyType> strategyTypes;
    private boolean throwExceptionOnCreate = false;

    @Inject
    public FakeStrategyManager() {
      this(ImmutableList.of(StrategyType.SMA_RSI));
    }

    public FakeStrategyManager(List<StrategyType> strategyTypes) {
      this.strategyTypes = strategyTypes;
    }

    public void setThrowExceptionOnCreate(boolean flag) {
      this.throwExceptionOnCreate = flag;
    }

    @Override
    public ImmutableList<StrategyType> getStrategyTypes() {
      return ImmutableList.copyOf(strategyTypes);
    }

    @Override
    public Any getDefaultParameters(StrategyType type) {
      return Any.getDefaultInstance();
    }

    @Override
    public org.ta4j.core.Strategy createStrategy(
        BarSeries series, StrategyType type, Any parameters) throws InvalidProtocolBufferException {
      if (throwExceptionOnCreate) {
        throw new InvalidProtocolBufferException("Forced exception for testing");
      }
      return new TestStrategy(type, parameters);
    }

    @Override
    public StrategyFactory<?> getStrategyFactory(StrategyType type) {
      // Return a concrete implementation of StrategyFactory
      return new TestStrategyFactory(type);
    }
  }

  /** A test implementation of StrategyFactory for testing. */
  public static class TestStrategyFactory implements StrategyFactory<Message> {
    private final StrategyType type;

    public TestStrategyFactory(StrategyType type) {
      this.type = type;
    }

    @Override
    public org.ta4j.core.Strategy createStrategy(BarSeries series, Message parameters) {
      return new TestStrategy(type, Any.pack(parameters));
    }

    @Override
    public Message getDefaultParameters() {
      return Any.getDefaultInstance();
    }

    @Override
    public StrategyType getStrategyType() {
      return type;
    }
  }

  /**
   * A test strategy implementation that extends BaseStrategy. This captures the strategy type and
   * parameters for testing.
   */
  public static class TestStrategy extends BaseStrategy {
    private final StrategyType type;
    private final Any parameters;

    public TestStrategy(StrategyType type, Any parameters) {
      // Use a simple BooleanRule for entry and exit
      super(new BooleanRule(false), new BooleanRule(false));
      this.type = type;
      this.parameters = parameters;
    }

    public StrategyType getType() {
      return type;
    }

    public Any getParameters() {
      return parameters;
    }

    @Override
    public boolean equals(Object obj) {
      if (this == obj) return true;
      if (obj == null || getClass() != obj.getClass()) return false;
      TestStrategy other = (TestStrategy) obj;
      return type == other.type && parameters.equals(other.parameters);
    }

    @Override
    public int hashCode() {
      return 31 * type.hashCode() + parameters.hashCode();
    }
  }
}
