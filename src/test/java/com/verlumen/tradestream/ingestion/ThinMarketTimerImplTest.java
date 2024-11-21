package com.verlumen.tradestream.ingestion;

import static com.google.common.truth.Truth.assertThat;

import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.testing.fieldbinder.Bind;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import com.google.common.collect.ImmutableList;
import org.junit.Before;
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
    @Inject private ThinMarketTimerTask thinMarketTimerTask;

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
        assertEquals("Delay should be 0", 0L, delayCaptor.getValue().longValue());
        assertEquals("Period should be one minute in milliseconds", 60_000L, periodCaptor.getValue().longValue());
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
        verify(timer, times(1)).scheduleAtFixedRate(eq(task), eq(0L), eq(60_000L));
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
    public void constructor_withNullTask_throwsNullPointerException() {
        // Arrange

        // Act & Assert
        try {
            new ThinMarketTimerImpl(null, timer);
            fail("Constructor should throw NullPointerException when task is null");
        } catch (NullPointerException e) {
            // Expected exception
            assertEquals("Expected NullPointerException", NullPointerException.class, e.getClass());
        }
    }

    @Test
    public void constructor_withNullTimer_throwsNullPointerException() {
        // Arrange

        // Act & Assert
        try {
            new ThinMarketTimerImpl(task, null);
            fail("Constructor should throw NullPointerException when timer is null");
        } catch (NullPointerException e) {
            // Expected exception
            assertEquals("Expected NullPointerException", NullPointerException.class, e.getClass());
        }
    }

    @Test
    public void start_taskAlreadyScheduled_doesNotReschedule() {
        // Arrange
        thinMarketTimer.start();

        // Act
        thinMarketTimer.start();

        // Assert
        verify(timer, times(1)).scheduleAtFixedRate(eq(task), anyLong(), anyLong());
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
