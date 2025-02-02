package com.verlumen.tradestream.time;

public enum TimeFrame {
    FIVE_MIN("5m", 5),
    FIFTEEN_MIN("15m", 15),
    THIRTY_MIN("30m", 30),
    ONE_HOUR("1h", 60),
    TWO_HOUR("2h", 120),
    FOUR_HOUR("4h", 240),
    EIGHT_HOUR("8h", 480),
    ONE_DAY("1d", 390),
    TWO_DAY("2d", 780),
    THREE_DAY("3d", 1170),
    FIVE_DAY("5d", 1950),
    ONE_WEEK("1w", 1950),
    TWO_WEEK("2w", 3900),
    THREE_WEEK("3w", 5850),
    ONE_MONTH("1M", 8190),
    TWO_MONTH("2M", 16380),
    THREE_MONTH("3M", 24570),
    FOUR_MONTH("4M", 32760),
    SIX_MONTH("6M", 49140),
    ONE_YEAR("1Y", 98280);

    private final String label;
    private final int minutes;

    TimeFrame(String label, int minutes) {
        this.label = label;
        this.minutes = minutes;
    }

    public String getLabel() {
        return label;
    }

    public int getMinutes() {
        return minutes;
    }

    public static TimeFrame fromMinutes(int minutes) {
        return Arrays.stream(values())
                .filter(tf -> tf.minutes == minutes)
                .findFirst()
                .orElseThrow(() -> new IllegalArgumentException("No TimeFrame for " + minutes + " minutes"));
    }
}
