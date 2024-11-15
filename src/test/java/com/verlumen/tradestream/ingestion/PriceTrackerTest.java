package com.verlumen.tradestream.ingestion;

import static com.google.common.truth.Truth.assertThat;

import com.google.inject.Guice;
import com.google.inject.Inject;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import com.google.testing.junit.testparameterinjector.TestParameterInjector;

@RunWith(TestParameterInjector.class)
public class PriceTrackerTest {
    private static final String TEST_PAIR = "BTC/USD";
    @Inject private PriceTracker tracker;

    @Before
    public void setUp() {
        Guice.createInjector().injectMembers(this);
    }

    @Test
    public void getLastPrice_noPrice_returnsNaN() {
        assertThat(tracker.getLastPrice(TEST_PAIR)).isNaN();
    }

    @Test
    public void updateLastPrice_updatesPrice() {
        tracker.updateLastPrice(TEST_PAIR, 100.0);
        assertThat(tracker.getLastPrice(TEST_PAIR)).isEqualTo(100.0);
    }

    @Test
    public void updateLastPrice_overwritesPreviousPrice() {
        tracker.updateLastPrice(TEST_PAIR, 100.0);
        tracker.updateLastPrice(TEST_PAIR, 200.0);
        assertThat(tracker.getLastPrice(TEST_PAIR)).isEqualTo(200.0);
    }

    @Test
    public void hasPrice_returnsCorrectState() {
        assertThat(tracker.hasPrice(TEST_PAIR)).isFalse();
        tracker.updateLastPrice(TEST_PAIR, 100.0);
        assertThat(tracker.hasPrice(TEST_PAIR)).isTrue();
    }

    @Test
    public void clear_removesAllPrices() {
        tracker.updateLastPrice(TEST_PAIR, 100.0);
        tracker.updateLastPrice("ETH/USD", 2000.0);
        
        tracker.clear();
        
        assertThat(tracker.hasPrice(TEST_PAIR)).isFalse();
        assertThat(tracker.hasPrice("ETH/USD")).isFalse();
    }
}
