package com.verlumen.tradestream.ingestion;

import static org.mockito.Mockito.*;
import static com.google.common.truth.Truth.assertThat;

import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.testing.fieldbinder.Bind;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import info.bitrich.xchangestream.core.StreamingExchange;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.mockito.Mock;
import org.mockito.junit.MockitoJUnit;
import org.mockito.junit.MockitoRule;

import java.util.concurrent.TimeUnit;

@RunWith(JUnit4.class)
public class WebSocketHealthMonitorTest {
    @Rule public MockitoRule mocks = MockitoJUnit.rule();

    @Mock @Bind private StreamingExchange mockExchange;
    @Mock @Bind private ScheduledExecutorService mockScheduler;
    @Inject private WebSocketHealthMonitor monitor;

    private ScheduledFuture<?> mockFuture;

    @Before
    public void setUp() {
        mockFuture = mock(ScheduledFuture.class);
        // Mock the scheduler's scheduleAtFixedRate to capture and verify the runnable
        when(mockScheduler.scheduleAtFixedRate(
            any(Runnable.class), 
            anyLong(), 
            anyLong(), 
            any(TimeUnit.class)
        )).thenReturn(mockFuture);

        Guice.createInjector(BoundFieldModule.of(this)).injectMembers(this);
    }

    @Test
    public void start_schedulesHealthCheck() {
        // Act
        monitor.start();

        // Assert
        verify(mockScheduler).scheduleAtFixedRate(
            any(Runnable.class),
            eq(30L), // Initial delay
            eq(30L), // Period
            eq(TimeUnit.SECONDS)
        );
    }

    @Test
    public void stop_shutsDownScheduler() {
        // Arrange
        monitor.start();

        // Act
        monitor.stop();

        // Assert
        verify(mockScheduler).shutdown();
    }

    @Test
    public void checkHealth_logsWarning_whenDisconnected() {
        // Arrange
        when(mockExchange.isAlive()).thenReturn(false);

        // Capture the runnable when scheduling
        ArgumentCaptor<Runnable> runnableCaptor = ArgumentCaptor.forClass(Runnable.class);
        monitor.start();
        verify(mockScheduler).scheduleAtFixedRate(
            runnableCaptor.capture(),
            anyLong(),
            anyLong(),
            any()
        );

        // Act
        runnableCaptor.getValue().run();

        // Assert
        verify(mockExchange).isAlive();
    }

    @Test
    public void stop_waitsForTermination() throws InterruptedException {
        // Arrange
        when(mockScheduler.awaitTermination(anyLong(), any()))
            .thenReturn(true);
        monitor.start();

        // Act
        monitor.stop();

        // Assert
        verify(mockScheduler).awaitTermination(5, TimeUnit.SECONDS);
    }
}
