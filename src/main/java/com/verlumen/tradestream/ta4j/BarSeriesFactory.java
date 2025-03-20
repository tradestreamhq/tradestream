package com.verlumen.tradestream.ta4j;

import com.google.common.collect.ImmutableList;
import com.verlumen.tradestream.marketdata.Candle;
import java.io.Serializable;
import java.util.List;
import org.ta4j.core.BarSeries;

/**
 * Factory interface for creating {@link BarSeries} instances from market data candles.
 *
 * <p>This interface defines methods for converting lists of
 * {@link com.verlumen.tradestream.marketdata.Candle} objects into a {@link BarSeries} object,
 * which represents a sequence of trading bars used for technical analysis in TA4J-based systems.
 * Implementations of this interface are responsible for defining the conversion logic,
 * including mapping candle attributes to bar properties.
 *
 * <p>Example usage:
 * <pre>{@code
 * // Using ImmutableList
 * ImmutableList<Candle> candles = ...
 * BarSeriesFactory factory = new MyBarSeriesFactoryImpl();
 * BarSeries series = factory.createBarSeries(candles);
 *
 * // Using regular List
 * List<Candle> candleList = ...
 * BarSeries seriesFromList = factory.createBarSeries(candleList);
 * }</pre>
 *
 * @see org.ta4j.core.BarSeries
 * @see com.verlumen.tradestream.marketdata.Candle
 */
public interface BarSeriesFactory extends Serializable {

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

    /**
     * Overload that accepts a regular {@link List} of {@link Candle} objects.
     * <p>
     * Internally, this method creates an {@link ImmutableList} from the provided list
     * and then delegates to {@link #createBarSeries(ImmutableList)}.
     *
     * @param candles a {@link List} of {@link Candle} instances representing market data
     * @return a {@link BarSeries} constructed from the provided candles
     * @throws IllegalArgumentException if the candles list is null or empty
     */
    default BarSeries createBarSeries(List<Candle> candles) {
        return createBarSeries(ImmutableList.copyOf(candles));
    }
}
