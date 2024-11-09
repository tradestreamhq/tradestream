package com.verlumen.tradestream.ingestion;

import static com.google.common.truth.Truth.assertThat;

import com.google.testing.junit.testparameterinjector.TestParameter;
import com.google.testing.junit.testparameterinjector.TestParameterInjector;
import org.junit.Test;
import org.junit.runner.RunWith;

@RunWith(TestParameterInjector.class)
public final class CandleKeyTest {

    enum CandleKeyTestCase {
        CASE1("trade-1", 1678886400000L),
        CASE2("trade-2", 1678886460000L),
        CASE3("trade-3", 1700000000000L);

        final String tradeId;
        final long minuteTimestamp;

        CandleKeyTestCase(String tradeId, long minuteTimestamp) {
            this.tradeId = tradeId;
            this.minuteTimestamp = minuteTimestamp;
        }

        CandleKey createCandleKey() {
            return new CandleKey(tradeId, minuteTimestamp);
        }
    }

    @Test
    public void equals_sameInstance_isTrue(
            @TestParameter CandleKeyTestCase testCase) {
        // Arrange
        CandleKey candleKey = testCase.createCandleKey();

        // Act & Assert
        assertThat(candleKey.equals(candleKey)).isTrue();
    }

    @Test
    public void equals_equivalentInstance_isTrue(
            @TestParameter CandleKeyTestCase testCase) {
        // Arrange
        CandleKey candleKey1 = testCase.createCandleKey();
        CandleKey candleKey2 = testCase.createCandleKey();

        // Act & Assert
        assertThat(candleKey1).isEqualTo(candleKey2);
    }

    @Test
    public void equals_differentInstance_isFalse(
            @TestParameter CandleKeyTestCase testCase1,
            @TestParameter CandleKeyTestCase testCase2) {
        if (testCase1 == testCase2) {
            return; // Skip identical test cases
        }

        // Arrange
        CandleKey candleKey1 = testCase1.createCandleKey();
        CandleKey candleKey2 = testCase2.createCandleKey();

        // Act & Assert
        assertThat(candleKey1).isNotEqualTo(candleKey2);
    }

    @Test
    public void hashCode_equalObjects_haveSameHashCode(
            @TestParameter CandleKeyTestCase testCase) {
        // Arrange
        CandleKey candleKey1 = testCase.createCandleKey();
        CandleKey candleKey2 = testCase.createCandleKey();

        // Act & Assert
        assertThat(candleKey1.hashCode()).isEqualTo(candleKey2.hashCode());
    }

    @Test
    public void hashCode_differentObjects_haveDifferentHashCodes(
            @TestParameter CandleKeyTestCase testCase1,
            @TestParameter CandleKeyTestCase testCase2) {
        if (testCase1 == testCase2) {
            return; // Skip identical test cases
        }

        // Arrange
        CandleKey candleKey1 = testCase1.createCandleKey();
        CandleKey candleKey2 = testCase2.createCandleKey();

        // Act & Assert
        assertThat(candleKey1.hashCode()).isNotEqualTo(candleKey2.hashCode());
    }

    @Test
    public void getters_returnExpectedValues(
            @TestParameter CandleKeyTestCase testCase) {
        // Arrange
        CandleKey candleKey = testCase.createCandleKey();

        // Act & Assert
        assertThat(candleKey.getTradeId()).isEqualTo(testCase.tradeId);
        assertThat(candleKey.getMinuteTimestamp()).isEqualTo(testCase.minuteTimestamp);
    }
}
