package com.verlumen.tradestream.time;

import static com.google.common.truth.Truth.assertThat;

import com.google.protobuf.Timestamp;
import java.time.Instant;
import java.time.ZoneId;
import java.time.ZonedDateTime;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;

@RunWith(JUnit4.class)
public class TimestampsTest {
    private static final long TEST_SECONDS = 1234567890L;
    private static final int TEST_NANOS = 123456789;

    @Test
    public void toZonedDateTime_convertsTimestampCorrectly() {
        // Arrange
        Timestamp timestamp = Timestamp.newBuilder()
            .setSeconds(TEST_SECONDS)
            .setNanos(TEST_NANOS)
            .build();

        // Act
        ZonedDateTime result = Timestamps.toZonedDateTime(timestamp);

        // Assert
        assertThat(result.toInstant().getEpochSecond()).isEqualTo(TEST_SECONDS);
        assertThat(result.toInstant().getNano()).isEqualTo(TEST_NANOS);
        assertThat(result.getZone()).isEqualTo(ZoneId.systemDefault());
    }

    @Test
    public void toTimestamp_convertsZonedDateTimeCorrectly() {
        // Arrange
        ZonedDateTime dateTime = ZonedDateTime.ofInstant(
            Instant.ofEpochSecond(TEST_SECONDS, TEST_NANOS),
            ZoneId.systemDefault());

        // Act
        Timestamp result = Timestamps.toTimestamp(dateTime);

        // Assert
        assertThat(result.getSeconds()).isEqualTo(TEST_SECONDS);
        assertThat(result.getNanos()).isEqualTo(TEST_NANOS);
    }

    @Test
    public void roundTripConversion_preservesValues() {
        // Arrange
        Timestamp original = Timestamp.newBuilder()
            .setSeconds(TEST_SECONDS)
            .setNanos(TEST_NANOS)
            .build();

        // Act
        ZonedDateTime dateTime = Timestamps.toZonedDateTime(original);
        Timestamp result = Timestamps.toTimestamp(dateTime);

        // Assert
        assertThat(result).isEqualTo(original);
    }
}
