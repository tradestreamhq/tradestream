package com.verlumen.tradestream.ta4j;

import com.google.common.collect.ImmutableList;
import com.verlumen.tradestream.marketdata.Candle;
import org.ta4j.core.BarSeries;

/**
 * Factory interface for creating {@link BarSeries} instances from market data candles.
 *
 * <p>This interface defines a single method for converting an immutable list of
 * {@link com.verlumen.tradestream.marketdata.Candle} objects into a {@link BarSeries} object,
 * which represents a sequence of trading bars used for technical analysis in TA4J-based systems.
 * Implementations of this interface are responsible for defining the conversion logic,
 * including mapping candle attributes to bar properties.
 *
 * <p>Example usage:
 * <pre>{@code
 * ImmutableList<Candle> candles = ...;
 * BarSeriesFactory factory = new MyBarSeriesFactoryImpl();
 * BarSeries series = factory.createBarSeries(candles);
 * }</pre>
 *
 * @see org.ta4j.core.BarSeries
 * @see com.verlumen.tradestream.marketdata.Candle
 */
public interface BarSeriesFactory {

    /**
     * Creates a {@link BarSeries} from an immutable list of {@link Candle} objects.
     *
     * <p>The implementation of this method should convert each candle in the provided list
     * into a corresponding trading bar, aggregating these bars into a {@link BarSeries} suitable
     * for technical analysis. Implementations may assume that the list is sorted in chronological order.
     *
     * @param candles an {@link ImmutableList} of {@link Candle} instances representing market data
     * @return a {@link BarSeries} constructed from the provided candles
     * @throws IllegalArgumentException if the candles list is null or empty
     */
    BarSeries createBarSeries(ImmutableList<Candle> candles);
}
