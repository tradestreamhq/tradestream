package com.verlumen.tradestream.strategies;

import static org.junit.Assert.*;

import com.google.common.collect.ImmutableList;
import com.google.inject.AbstractModule;
import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.Injector;
import com.google.inject.testing.fieldbinder.Bind;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import com.google.protobuf.Message;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashSet;
import java.util.Set;
import org.junit.Before;
import org.junit.Test;
import org.ta4j.core.BaseBarSeries;
import org.ta4j.core.BaseStrategy;
import org.ta4j.core.BarSeries;
import org.ta4j.core.rules.BooleanRule;

/**
 * JUnit4 tests for StrategyStateImpl.
 */
public class StrategyStateImplTest {

    @Bind
    private StrategyStateImpl strategyState;

    @Bind
    private FakeStrategyManager fakeStrategyManager;

    // Use BaseBarSeries from ta4j
    private BarSeries dummyBarSeries = new BaseBarSeries("DummyBarSeries");

    @Before
    public void setUp() {
        Guice.createInjector(BoundFieldModule.of(this)).injectMembers(this);
    }

    // --- getCurrentStrategy() tests ---

    @Test
    public void testGetCurrentStrategyCreatesNonNullStrategy() throws Exception {
        // Arrange & Act
        org.ta4j.core.Strategy result = strategyState.getCurrentStrategy(dummyBarSeries);
        // Assert: a non-null strategy is returned.
        assertNotNull(result);
    }

    @Test
    public void testGetCurrentStrategyCreatesStrategyWithDefaultType() throws Exception {
        // Arrange & Act
        org.ta4j.core.Strategy result = strategyState.getCurrentStrategy(dummyBarSeries);
        // Assert: the created strategy (our test strategy) records type SMA_RSI.
        TestStrategy ts = (TestStrategy) result;
        assertEquals(StrategyType.SMA_RSI, ts.getType());
    }

    @Test
    public void testGetCurrentStrategyReturnsSameInstanceOnSubsequentCalls() throws Exception {
        // Arrange
        org.ta4j.core.Strategy first = strategyState.getCurrentStrategy(dummyBarSeries);
        // Act
        org.ta4j.core.Strategy second = strategyState.getCurrentStrategy(dummyBarSeries);
        // Assert: the same instance is returned.
        assertSame(first, second);
    }

    // --- updateRecord() tests ---

    @Test
    public void testUpdateRecordDoesNotChangeCurrentStrategyUntilReselect() throws Exception {
        // Arrange
        org.ta4j.core.Strategy initial = strategyState.getCurrentStrategy(dummyBarSeries);
        Any newParams = Any.getDefaultInstance();
        // Act
        strategyState.updateRecord(StrategyType.SMA_RSI, newParams, 100.0);
        // Assert: the cached strategy remains unchanged.
        assertSame(initial, strategyState.getCurrentStrategy(dummyBarSeries));
    }

    // --- selectBestStrategy() tests ---

    @Test
    public void testSelectBestStrategyPicksRecordWithHighestScore() {
        // Arrange
        Any paramsDummy = Any.getDefaultInstance();
        strategyState.updateRecord(StrategyType.SMA_RSI, paramsDummy, 100.0);
        // Act
        strategyState.selectBestStrategy(dummyBarSeries);
        // Assert: the current strategy type is updated to SMA_RSI.
        assertEquals(StrategyType.SMA_RSI, strategyState.getCurrentStrategyType());
    }

    @Test(expected = IllegalStateException.class)
    public void testSelectBestStrategyThrowsWhenNoRecordsAvailable() {
        // Arrange – use a fake manager with no strategy types.
        FakeStrategyManager emptyManager = new FakeStrategyManager(Collections.<StrategyType>emptyList());
        Injector injector = Guice.createInjector(
            BoundFieldModule.of(this),
            new AbstractModule() {
                @Override
                protected void configure() {
                    bind(StrategyManager.class).toInstance(emptyManager);
                    bind(FakeStrategyManager.class).toInstance(emptyManager);
                }
            }
        );
        injector.injectMembers(this);
        // Act: should throw IllegalStateException.
        strategyState.selectBestStrategy(dummyBarSeries);
    }

    @Test(expected = InvalidProtocolBufferException.class)
    public void testGetCurrentStrategyThrowsWhenStrategyCreationFails() throws Exception {
        // Arrange – force createStrategy to throw an exception.
        fakeStrategyManager.setThrowExceptionOnCreate(true);
        // Act: getCurrentStrategy should throw.
        strategyState.getCurrentStrategy(dummyBarSeries);
    }

    @Test(expected = RuntimeException.class)
    public void testSelectBestStrategyThrowsWhenStrategyCreationFails() {
        // Arrange – update record then force exception on creation.
        Any paramsDummy = Any.getDefaultInstance();
        strategyState.updateRecord(StrategyType.SMA_RSI, paramsDummy, 100.0);
        fakeStrategyManager.setThrowExceptionOnCreate(true);
        // Act: selectBestStrategy should wrap the exception in a RuntimeException.
        strategyState.selectBestStrategy(dummyBarSeries);
    }

    // --- toStrategyMessage() tests ---

    @Test
    public void testToStrategyMessageReturnsCorrectType() {
        // Arrange
        Any paramsDummy = Any.getDefaultInstance();
        strategyState.updateRecord(StrategyType.SMA_RSI, paramsDummy, 100.0);
        strategyState.selectBestStrategy(dummyBarSeries);
        // Act
        // Use fully qualified name to avoid confusion with org.ta4j.core.Strategy
        com.verlumen.tradestream.strategies.Strategy protoMessage = strategyState.toStrategyMessage();
        // Assert: the proto message type is SMA_RSI.
        assertEquals(StrategyType.SMA_RSI, protoMessage.getType());
    }

    @Test
    public void testToStrategyMessageReturnsCorrectParameters() {
        // Arrange
        Any paramsDummy = Any.getDefaultInstance();
        strategyState.updateRecord(StrategyType.SMA_RSI, paramsDummy, 100.0);
        strategyState.selectBestStrategy(dummyBarSeries);
        // Act
        // Use fully qualified name to avoid confusion with org.ta4j.core.Strategy
        com.verlumen.tradestream.strategies.Strategy protoMessage = strategyState.toStrategyMessage();
        // Assert: the proto message parameters match the expected value.
        assertEquals(paramsDummy, protoMessage.getParameters());
    }

    // --- getters tests ---

    @Test
    public void testGetStrategyTypesReturnsAllExpectedTypes() {
        // Arrange & Act
        Iterable<StrategyType> types = strategyState.getStrategyTypes();
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
        // Act
        StrategyType currentType = strategyState.getCurrentStrategyType();
        // Assert: default is SMA_RSI.
        assertEquals(StrategyType.SMA_RSI, currentType);
    }

    // --- Supporting fake and test classes for testing ---

    /**
     * A fake StrategyManager that simulates behavior for testing.
     */
    public static class FakeStrategyManager implements StrategyManager {
        private final Iterable<StrategyType> strategyTypes;
        private boolean throwExceptionOnCreate = false;

        @Inject
        public FakeStrategyManager() {
            this(Arrays.asList(StrategyType.SMA_RSI));
        }

        public FakeStrategyManager(Iterable<StrategyType> strategyTypes) {
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
        public org.ta4j.core.Strategy createStrategy(BarSeries series, StrategyType type, Any parameters)
                throws InvalidProtocolBufferException {
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

    /**
     * A test implementation of StrategyFactory for testing.
     */
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
     * A test strategy implementation that extends BaseStrategy.
     * This captures the strategy type and parameters for testing.
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
            if (this == obj)
                return true;
            if (obj == null || getClass() != obj.getClass())
                return false;
            TestStrategy other = (TestStrategy) obj;
            return type == other.type && parameters.equals(other.parameters);
        }

        @Override
        public int hashCode() {
            return 31 * type.hashCode() + parameters.hashCode();
        }
    }
}
