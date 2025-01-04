package com.verlumen.tradestream.time;

import com.google.protobuf.Timestamp;
import java.time.Instant;
import java.time.ZoneId;
import java.time.ZonedDateTime;

/** Utility methods for time conversions between Protobuf and Java time types. */
public final class Timestamps {
    /** Convert a Protobuf Timestamp to ZonedDateTime. */
    public static ZonedDateTime toZonedDateTime(Timestamp timestamp) {
        return ZonedDateTime.ofInstant(
            Instant.ofEpochSecond(
                timestamp.getSeconds(),
                timestamp.getNanos()),
            ZoneId.systemDefault());
    }

    /** Convert an epoch timestamp (milliseconds) to Protobuf Timestamp. */
    public static Timestamp toTimestamp(long epochMillis) {
        return toTimestamp(Instant.ofEpochMilli(epochMillis));
    }

    /** Convert a ZonedDateTime to Protobuf Timestamp. */
    public static Timestamp toTimestamp(ZonedDateTime dateTime) {
        return toTimestamp(dateTime.toInstant());
    }

    private static Timestamp toTimestamp(Instant instant) {
        return Timestamp.newBuilder()
            .setSeconds(instant.getEpochSecond())
            .setNanos(instant.getNano())
            .build();
    }

    private Timestamps() {} // Prevent instantiation
}
