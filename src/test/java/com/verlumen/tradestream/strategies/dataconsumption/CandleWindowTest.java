
/**
 * Tests specific to the CandleWindow functionality
 */
@RunWith(JUnit4.class)
public class CandleWindowTest {
    private static final String CURRENCY_PAIR = "BTC/USD";
    private static final Duration TIMEFRAME = Duration.ofMinutes(1);
    private CandleWindow window;

    @Before
    public void setUp() {
        window = new CandleWindow(TIMEFRAME);
    }

    @Test
    public void addCandle_maintainsChronologicalOrder() {
        // Arrange
        Candle candle1 = createTestCandle(1000L);
        Candle candle2 = createTestCandle(2000L);
        Candle candle3 = createTestCandle(3000L);

        // Act
        window.addCandle(candle2);
        window.addCandle(candle1);
        window.addCandle(candle3);

        List<Candle> candles = window.getCandles(3);

        // Assert
        assertThat(candles).hasSize(3);
        assertThat(candles.get(0).getTimestamp()).isEqualTo(1000L);
        assertThat(candles.get(1).getTimestamp()).isEqualTo(2000L);
        assertThat(candles.get(2).getTimestamp()).isEqualTo(3000L);
    }

    private static Candle createTestCandle(long timestamp) {
        return Candle.newBuilder()
            .setTimestamp(timestamp)
            .setCurrencyPair(CURRENCY_PAIR)
            .build();
    }
}
