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
import java.time.Duration;
import java.time.ZonedDateTime;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashSet;
import java.util.Set;
import org.junit.Before;
import org.junit.Test;
import org.ta4j.core.BarSeries;
import org.ta4j.core.Bar;
import org.ta4j.core.num.Num;

/**
 * JUnit4 tests for StrategyStateImpl.
 *
 * This suite uses Guice injection (with BoundFieldModule) and the real protobuf-generated
 * Strategy message (imported from the production code) for verifying behavior. Each test
 * follows the arrange–act–assert pattern with a single assertion.
 */
public class StrategyStateImplTest {

    @Bind
    private StrategyStateImpl strategyState;

    @Bind
    private FakeStrategyManager fakeStrategyManager;

    // A dummy BarSeries for testing
    private BarSeries dummyBarSeries = new DummyBarSeries();

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
        // Assert: the created strategy (our dummy) records type SMA_RSI.
        DummyStrategy ds = (DummyStrategy) result;
        assertEquals(StrategyType.SMA_RSI, ds.getType());
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
    // These tests verify that the real protobuf Strategy message is built correctly.

    @Test
    public void testToStrategyMessageReturnsCorrectType() {
        // Arrange
        Any paramsDummy = Any.getDefaultInstance();
        strategyState.updateRecord(StrategyType.SMA_RSI, paramsDummy, 100.0);
        strategyState.selectBestStrategy(dummyBarSeries);
        // Act
        Strategy protoMessage = strategyState.toStrategyMessage();
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
        Strategy protoMessage = strategyState.toStrategyMessage();
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

    // --- Supporting fake and dummy classes for testing ---

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
            return new DummyStrategy(type, parameters);
        }
        
        @Override
        public StrategyFactory<?> getStrategyFactory(StrategyType type) {
            // Return a concrete implementation of StrategyFactory
            return new DummyStrategyFactory(type);
        }
    }
    
    /**
     * A dummy implementation of StrategyFactory for testing.
     */
    public static class DummyStrategyFactory implements StrategyFactory<Message> {
        private final StrategyType type;
        
        public DummyStrategyFactory(StrategyType type) {
            this.type = type;
        }
        
        @Override
        public org.ta4j.core.Strategy createStrategy(BarSeries series, Message parameters) {
            return new DummyStrategy(type, Any.pack(parameters));
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
     * A dummy implementation of the TA4J Strategy interface.
     * This dummy records its associated StrategyType and parameters.
     */
    public static class DummyStrategy implements org.ta4j.core.Strategy {

        private final StrategyType type;
        private final Any parameters;
        private int unstableBars = 0;
        private String name = "DummyStrategy";

        public DummyStrategy(StrategyType type, Any parameters) {
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
            DummyStrategy other = (DummyStrategy) obj;
            return type == other.type && parameters.equals(other.parameters);
        }

        @Override
        public int hashCode() {
            return 31 * type.hashCode() + parameters.hashCode();
        }
        
        @Override
        public boolean shouldEnter(int index) {
            return false;
        }
        
        @Override
        public boolean shouldExit(int index) {
            return false;
        }
        
        @Override
        public boolean isUnstableAt(int index) {
            return false;
        }
        
        @Override
        public int getUnstableBars() {
            return unstableBars;
        }
        
        @Override
        public void setUnstableBars(int unstableBars) {
            this.unstableBars = unstableBars;
        }
        
        @Override
        public org.ta4j.core.Strategy opposite() {
            return this; // For testing purposes, return self
        }
        
        @Override
        public org.ta4j.core.Strategy or(String name, org.ta4j.core.Strategy strategy, int unstablePeriod) {
            return this; // For testing purposes, return self
        }
        
        @Override
        public org.ta4j.core.Strategy or(org.ta4j.core.Strategy strategy) {
            return this; // For testing purposes, return self
        }
        
        @Override
        public org.ta4j.core.Strategy and(String name, org.ta4j.core.Strategy strategy, int unstablePeriod) {
            return this; // For testing purposes, return self
        }
        
        @Override
        public org.ta4j.core.Strategy and(org.ta4j.core.Strategy strategy) {
            return this; // For testing purposes, return self
        }
        
        @Override
        public org.ta4j.core.Strategy xor(String name, org.ta4j.core.Strategy strategy, int unstablePeriod) {
            return this; // For testing purposes, return self
        }
        
        @Override
        public org.ta4j.core.Strategy xor(org.ta4j.core.Strategy strategy) {
            return this; // For testing purposes, return self
        }
        
        @Override
        public String getName() {
            return name;
        }
    }

    /**
     * A minimal dummy implementation of BarSeries.
     */
    public static class DummyBarSeries implements BarSeries {
        // Implement required methods
        
        @Override
        public String getName() {
            return "DummyBarSeries";
        }
        
        @Override
        public Bar getBar(int i) {
            return null;
        }
        
        @Override
        public int getBarCount() {
            return 0;
        }
        
        @Override
        public int getBeginIndex() {
            return 0;
        }
        
        @Override
        public int getEndIndex() {
            return 0;
        }
        
        @Override
        public void setMaximumBarCount(int maximumBarCount) {
            // No implementation needed for testing
        }
        
        @Override
        public int getMaximumBarCount() {
            return 0;
        }
        
        @Override
        public int getRemovedBarsCount() {
            return 0;
        }
        
        @Override
        public Num numOf(Number number) {
            return null;
        }
        
        @Override
        public BarSeries getSubSeries(int startIndex, int endIndex) {
            return this;
        }
        
        @Override
        public void addPrice(Num price) {
            // No implementation needed for testing
        }
        
        @Override
        public void addTrade(Num amount, Num price) {
            // No implementation needed for testing
        }
        
        @Override
        public void addBar(Duration timePeriod, ZonedDateTime endTime, Num openPrice, Num highPrice, 
                          Num lowPrice, Num closePrice, Num volume) {
            // No implementation needed for testing
        }
        
        @Override
        public void addBar(Duration timePeriod, ZonedDateTime endTime, Num openPrice, Num highPrice, 
                          Num lowPrice, Num closePrice, Num volume, Num amount) {
            // No implementation needed for testing
        }
    }
}
