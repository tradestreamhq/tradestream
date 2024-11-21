package com.verlumen.tradestream.ingestion;

import static com.google.common.truth.Truth.assertThat;
import static org.mockito.Mockito.times;

import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.testing.fieldbinder.Bind;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import com.google.common.collect.ImmutableList;
import org.junit.Before;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.junit.Rule;
import org.junit.Test;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.MockitoJUnit;
import org.mockito.junit.MockitoRule;

import java.util.Timer;
import java.util.TimerTask;

@RunWith(JUnit4.class)
public class ThinMarketTimerImplTest {
    @Rule public MockitoRule mocks = MockitoJUnit.rule();

    @Mock @Bind private CandleManager candleManager;
    @Mock @Bind private CurrencyPairSupplier currencyPairSupplier;
    @Mock @Bind private Timer timer;
    @Inject private ThinMarketTimerTask thinMarketTimer;

    @Before
    public void setUp() {
        Guice.createInjector(BoundFieldModule.of(this)).injectMembers(this);
    }

    @Test
    public void start_schedulesTaskAtFixedRate() {
        // Arrange
        ArgumentCaptor<Long> delayCaptor = ArgumentCaptor.forClass(Long.class);
        ArgumentCaptor<Long> periodCaptor = ArgumentCaptor.forClass(Long.class);

        // Act
        thinMarketTimer.start();

        // Assert
        verify(timer).scheduleAtFixedRate(eq(task), delayCaptor.capture(), periodCaptor.capture());
        assertThat(delayCaptor.getValue().longValue()).isEqualTo(0L);
        assertThat(periodCaptor.getValue().longValue()).isEqualTo(60_000L);
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
    public void start_afterStop_reschedulesTask() {
        // Arrange
        thinMarketTimer.start();
        thinMarketTimer.stop();

        // Act
        thinMarketTimer.start();

        // Assert
        verify(timer, times(2)).scheduleAtFixedRate(eq(task), eq(0L), eq(60_000L));
    }

    @Test
    public void start_multipleTimesWithoutStop_schedulesTaskOnlyOnce() {
        // Arrange

        // Act
        thinMarketTimer.start();
        thinMarketTimer.start();

        // Assert
        verify(timer).scheduleAtFixedRate(eq(task), eq(0L), eq(60_000L));
    }

    @Test
    public void stop_withoutStart_doesNotThrowException() {
        // Arrange

        // Act & Assert
        try {
            thinMarketTimer.stop();
        } catch (Exception e) {
            fail("Stopping without starting should not throw an exception");
        }
    }

    @Test
    public void start_taskAlreadyScheduled_doesNotReschedule() {
        // Arrange
        thinMarketTimer.start();

        // Act
        thinMarketTimer.start();

        // Assert
        verify(timer).scheduleAtFixedRate(eq(task), anyLong(), anyLong());
    }

    @Test
    public void stop_timerAlreadyCancelled_doesNotThrowException() {
        // Arrange
        thinMarketTimer.start();
        thinMarketTimer.stop();

        // Act & Assert
        try {
            thinMarketTimer.stop();
        } catch (Exception e) {
            fail("Stopping an already stopped timer should not throw an exception");
        }
    }
}
