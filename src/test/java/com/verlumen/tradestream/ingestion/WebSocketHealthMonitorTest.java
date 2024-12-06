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
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.MockitoJUnit;
import org.mockito.junit.MockitoRule;

import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.ScheduledFuture;
import java.util.concurrent.TimeUnit;

/**
 * Unit tests for WebSocketHealthMonitor.
 * Tests the health checking and reconnection logic using mocked dependencies.
 */
@RunWith(JUnit4.class)
public class WebSocketHealthMonitorTest {
    @Rule public MockitoRule mocks = MockitoJUnit.rule();

    @Mock @Bind private StreamingExchange mockExchange;
    @Mock @Bind private ScheduledExecutorService mockScheduler;
    @Mock private ScheduledFuture<?> mockFuture;
    @Inject private WebSocketHealthMonitor monitor;

    @Before
    public void setUp() {
        // Set up scheduler mock to return our mock future
        when(mockScheduler.scheduleAtFixedRate(
            any(Runnable.class),
            anyLong(),
            anyLong(),
            any(TimeUnit.class)
        )).thenReturn(mockFuture);

        // Set up exchange mock with default connection behavior
        when(mockExchange.connect()).thenReturn(CompletableFuture.completedFuture(null));
        when(mockExchange.disconnect()).thenReturn(CompletableFuture.completedFuture(null));

        // Create the monitor with injected mocks
        Guice.createInjector(BoundFieldModule.of(this)).injectMembers(this);
    }

    /**
     * Verify health check is scheduled when monitor starts
     */
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

    /**
     * Verify scheduler is shut down when monitor stops
     */
    @Test
    public void stop_shutsDownScheduler() {
        // Arrange
        monitor.start();

        // Act
        monitor.stop();

        // Assert
        verify(mockScheduler).shutdown();
    }

    /**
     * Verify warning is logged when connection is down
     */
    @Test
    public void checkHealth_logsWarning_whenDisconnected() {
        // Arrange
        when(mockExchange.isAlive()).thenReturn(false);

        // Capture the health check runnable
        ArgumentCaptor<Runnable> runnableCaptor = ArgumentCaptor.forClass(Runnable.class);
        monitor.start();
        verify(mockScheduler).scheduleAtFixedRate(
            runnableCaptor.capture(),
            anyLong(),
            anyLong(),
            any()
        );

        // Act - run the health check
        runnableCaptor.getValue().run();

        // Assert exchange status was checked
        verify(mockExchange).isAlive();
    }

    /**
     * Verify graceful shutdown with timeout
     */
    @Test
    public void stop_waitsForTermination() throws InterruptedException {
        // Arrange
        when(mockScheduler.awaitTermination(anyLong(), any()))
            .thenReturn(true);
        monitor.start();

        // Act
        monitor.stop();

        // Assert waited for termination
        verify(mockScheduler).awaitTermination(5, TimeUnit.SECONDS);
    }

    /**
     * Verify reconnection is attempted when connection is down
     */
    @Test
    public void checkHealth_attemptsReconnect_whenDisconnected() {
        // Arrange
        when(mockExchange.isAlive()).thenReturn(false);
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

        // Assert reconnection was attempted
        verify(mockExchange).disconnect();
        verify(mockExchange).connect();
    }

    /**
     * Verify monitor doesn't start if already running
     */
    @Test
    public void start_doesNothing_whenAlreadyRunning() {
        // Arrange
        monitor.start();
        clearInvocations(mockScheduler);

        // Act
        monitor.start();

        // Assert no new schedule was created
        verifyNoInteractions(mockScheduler);
    }
}
