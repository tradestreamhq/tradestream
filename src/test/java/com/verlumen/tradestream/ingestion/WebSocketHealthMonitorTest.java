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

@RunWith(JUnit4.class)
public class WebSocketHealthMonitorTest {
    @Rule public MockitoRule mocks = MockitoJUnit.rule();

    @Mock @Bind private StreamingExchange mockExchange;
    @Inject private WebSocketHealthMonitor monitor;

    @Before
    public void setUp() {
        Guice.createInjector(BoundFieldModule.of(this)).injectMembers(this);
    }

    @Test
    public void start_schedulesHealthCheck() throws InterruptedException {
        // Arrange
        when(mockExchange.isAlive()).thenReturn(true);

        // Act
        monitor.start();
        Thread.sleep(100); // Allow scheduled task to run

        // Assert
        verify(mockExchange, atLeastOnce()).isAlive();
    }

    @Test
    public void stop_shutsDownScheduler() throws InterruptedException {
        // Arrange
        monitor.start();

        // Act
        monitor.stop();
        Thread.sleep(100); // Allow shutdown to complete

        // Assert
        // Verify no more health checks after stop
        int callCount = mockingDetails(mockExchange).getInvocations().size();
        Thread.sleep(100);
        assertThat(mockingDetails(mockExchange).getInvocations().size())
            .isEqualTo(callCount);
    }

    @Test
    public void checkHealth_logsWarning_whenDisconnected() throws InterruptedException {
        // Arrange
        when(mockExchange.isAlive()).thenReturn(false);

        // Act
        monitor.start();
        Thread.sleep(100); // Allow scheduled task to run

        // Assert
        verify(mockExchange, atLeastOnce()).isAlive();
        // Note: Would ideally verify log message, but FluentLogger makes this difficult
        // Consider using a logging framework that's more testable if this is important
    }
}
