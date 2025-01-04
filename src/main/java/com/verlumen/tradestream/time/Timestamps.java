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
    
    /** Convert a ZonedDateTime to Protobuf Timestamp. */
    public static Timestamp toTimestamp(ZonedDateTime dateTime) {
        return Timestamp.newBuilder()
            .setSeconds(dateTime.toInstant().getEpochSecond())
            .setNanos(dateTime.toInstant().getNano())
            .build();
    }

    private Timestamps() {} // Prevent instantiation
}
