package com.verlumen.tradestream.ingestion;

import static com.google.common.truth.Truth.assertThat;

import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.testing.fieldbinder.Bind;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import com.google.common.collect.ImmutableList;
import org.junit.Before;
import org.junit.Test;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import java.util.Timer;
import org.mockito.Mock;
import org.mockito.junit.MockitoJUnit;
import org.mockito.junit.MockitoRule;

@RunWith(JUnit4.class)
public class ThinMarketTimerImplTest {
    @Rule public MockitoRule mocks = MockitoJUnit.rule();

    @Mock @Bind private CandleManager candleManager;
    @Mock @Bind private CurrencyPairSupplier currencyPairSupplier;
    @Mock @Bind private Timer timer;
    @Inject private ThinMarketTimerTask thinMarketTimerTask;

    @Before
    public void setUp() {
        Guice.createInjector(BoundFieldModule.of(this)).injectMembers(this);
    }

    @Test
    public void start_schedulesTimerTaskAtFixedRate() {
        // Arrange
        ArgumentCaptor<TimerTask> taskCaptor = ArgumentCaptor.forClass(TimerTask.class);
        long expectedPeriod = 60_000L;

        // Act
        thinMarketTimer.start();

        // Assert
        verify(timer).scheduleAtFixedRate(taskCaptor.capture(), eq(0L), eq(expectedPeriod));
        assertThat(taskCaptor.getValue()).isNotNull();
    }

    @Test
    public void stop_cancelsTimer() {
        // Arrange
        thinMarketTimer.start();

        // Act
        thinMarketTimer.stop();

        // Assert
        verify(timer).cancel();
    }

    @Test
    public void start_multipleCalls_scheduleOnlyOnce() {
        // Arrange

        // Act
        thinMarketTimer.start();
        thinMarketTimer.start();

        // Assert
        verify(timer, times(1)).scheduleAtFixedRate(any(TimerTask.class), anyLong(), anyLong());
    }

    @Test
    public void stop_withoutStart_doesNotThrowException() {
        // Act & Assert
        try {
            thinMarketTimer.stop();
        } catch (Exception e) {
            fail("Calling stop without start should not throw an exception");
        }
    }

    @Test
    public void start_afterStop_reschedulesTimerTask() {
        // Arrange
        thinMarketTimer.start();
        thinMarketTimer.stop();
        ArgumentCaptor<TimerTask> taskCaptor = ArgumentCaptor.forClass(TimerTask.class);

        // Act
        thinMarketTimer.start();

        // Assert
        verify(timer, times(2)).scheduleAtFixedRate(taskCaptor.capture(), eq(0L), eq(60_000L));
    }

    @Test
    public void timerTask_run_invokesHandleThinlyTradedMarkets() {
        // Arrange
        TimerTask timerTask = captureTimerTask();
        CurrencyPair currencyPair = new CurrencyPair("BTC/USD");
        when(currencyPairSupplier.currencyPairs()).thenReturn(java.util.Collections.singletonList(currencyPair));

        // Act
        timerTask.run();

        // Assert
        verify(candleManager).handleThinlyTradedMarkets(com.google.common.collect.ImmutableList.of("BTC/USD"));
    }

    @Test
    public void timerTask_run_withEmptyCurrencyPairs_invokesHandleThinlyTradedMarketsWithEmptyList() {
        // Arrange
        TimerTask timerTask = captureTimerTask();
        when(currencyPairSupplier.currencyPairs()).thenReturn(java.util.Collections.emptyList());

        // Act
        timerTask.run();

        // Assert
        verify(candleManager).handleThinlyTradedMarkets(com.google.common.collect.ImmutableList.of());
    }

    @Test(expected = NullPointerException.class)
    public void timerTask_run_withNullCurrencyPairs_throwsNullPointerException() {
        // Arrange
        TimerTask timerTask = captureTimerTask();
        when(currencyPairSupplier.currencyPairs()).thenReturn(null);

        // Act
        timerTask.run();

        // Act / Assert
        assertThrows(NullPointerException.class, timerTask::run)
    }

    // Helper method to capture the TimerTask scheduled by start()
    private TimerTask captureTimerTask() {
        ArgumentCaptor<TimerTask> taskCaptor = ArgumentCaptor.forClass(TimerTask.class);
        thinMarketTimer.start();
        verify(timer).scheduleAtFixedRate(taskCaptor.capture(), anyLong(), anyLong());
        return taskCaptor.getValue();
    }
}

