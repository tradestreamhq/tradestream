package com.verlumen.tradestream.ingestion;

import com.google.common.testing.EqualsTester;
import com.tngtech.java.junit.dataprovider.DataProvider;
import com.tngtech.java.junit.dataprovider.DataProviderRunner;
import com.tngtech.java.junit.dataprovider.UseDataProvider;
import org.junit.Test;
import org.junit.runner.RunWith;

import java.util.Objects;

import static com.google.common.truth.Truth.assertThat;

@RunWith(DataProviderRunner.class)
public final class CandleKeyTest {
    @DataProvider
    public static Object[][] equalCandleKeys() {
        return new Object[][]{
                {"trade-1", 1678886400000L},
                {"trade-2", 1678886460000L},
                {"trade-3", 1700000000000L}
        };
    }


    @Test
    @UseDataProvider("equalCandleKeys")
    public void equals_sameInstance_isTrue(String tradeId, long minuteTimestamp) {
        // Arrange
        CandleKey candleKey = new CandleKey(tradeId, minuteTimestamp);

        // Act
        boolean isEqual = candleKey.equals(candleKey);

        // Assert
        assertThat(isEqual).isTrue();
    }


    @Test
    @UseDataProvider("equalCandleKeys")
    public void equals_equivalentInstance_isTrue(String tradeId, long minuteTimestamp) {
        // Arrange
        CandleKey candleKey1 = new CandleKey(tradeId, minuteTimestamp);
        CandleKey candleKey2 = new CandleKey(tradeId, minuteTimestamp);


        // Act
        boolean isEqual = candleKey1.equals(candleKey2);

        // Assert
        assertThat(isEqual).isTrue();
    }

    @Test
    public void equals_differentInstance_isFalse() {
        // Arrange
        CandleKey candleKey1 = new CandleKey("trade-1", 1678886400000L);
        CandleKey candleKey2 = new CandleKey("trade-2", 1678886400000L);
        CandleKey candleKey3 = new CandleKey("trade-1", 1678886460000L);
        CandleKey candleKey4 = new CandleKey("trade-2", 1678886460000L);

        // Act & Assert
        new EqualsTester()
                .addEqualityGroup(candleKey1)
                .addEqualityGroup(candleKey2)
                .addEqualityGroup(candleKey3)
                .addEqualityGroup(candleKey4)
                .testEquals();
    }


    @Test
    @UseDataProvider("equalCandleKeys")
    public void hashCode_equalObjects_haveSameHashCode(String tradeId, long minuteTimestamp) {
        // Arrange
        CandleKey candleKey1 = new CandleKey(tradeId, minuteTimestamp);
        CandleKey candleKey2 = new CandleKey(tradeId, minuteTimestamp);

        // Act & Assert
        assertThat(candleKey1.hashCode()).isEqualTo(candleKey2.hashCode());
    }

    @Test
    public void hashCode_consistentWithEquals() {
        // Arrange
        CandleKey candleKey1 = new CandleKey("trade-1", 1678886400000L);
        CandleKey candleKey2 = new CandleKey("trade-2", 1678886400000L);
        CandleKey candleKey3 = new CandleKey("trade-1", 1678886460000L);
        CandleKey candleKey4 = new CandleKey("trade-2", 1678886460000L);

        // Act & Assert
        new EqualsTester()
                .addEqualityGroup(candleKey1)
                .addEqualityGroup(candleKey2)
                .addEqualityGroup(candleKey3)
                .addEqualityGroup(candleKey4)
                .testEquals();
    }

    @Test
    @UseDataProvider("equalCandleKeys")
    public void getters_returnExpectedValues(String tradeId, long minuteTimestamp) {
        // Arrange
        CandleKey candleKey = new CandleKey(tradeId, minuteTimestamp);

        // Act & Assert
        assertThat(candleKey.getTradeId()).isEqualTo(tradeId);
        assertThat(candleKey.getMinuteTimestamp()).isEqualTo(minuteTimestamp);
    }
}
