package com.verlumen.tradestream.marketregime;

/**
 * Represents the classified state of market conditions. Each regime suggests
 * different optimal trading approaches.
 */
public enum MarketRegime {
    TRENDING_UP("Sustained upward price movement with strong directional momentum"),
    TRENDING_DOWN("Sustained downward price movement with strong directional momentum"),
    RANGING("Sideways price action within a defined range, no clear trend"),
    HIGH_VOLATILITY("Large price swings with rapid directional changes"),
    LOW_VOLATILITY("Compressed price action with minimal movement");

    private final String description;

    MarketRegime(String description) {
        this.description = description;
    }

    public String getDescription() {
        return description;
    }
}
