package com.verlumen.tradestream.http;

import static com.google.common.truth.Truth.assertThat;
import static org.junit.Assert.assertThrows;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.*;

import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.testing.fieldbinder.Bind;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.mockito.Mock;
import org.mockito.junit.MockitoJUnit;
import org.mockito.junit.MockitoRule;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.net.HttpURLConnection;
import java.net.ProtocolException;
import java.util.Collections;
import java.util.HashMap;
import java.util.Map;

@RunWith(JUnit4.class)
public class HttpClientImplTest {
    @Rule public MockitoRule mocks = MockitoJUnit.rule();

    @Mock @Bind private HttpURLConnectionFactory mockConnectionFactory;
    @Mock private HttpURLConnection mockConnection;

    @Inject private HttpClientImpl httpClient;

    @Before
    public void setUp() throws Exception {
        Guice.createInjector(BoundFieldModule.of(this)).injectMembers(this);
        when(mockConnectionFactory.create(anyString())).thenReturn(mockConnection);
    }

    @Test
    public void get_returnsResponse_whenHttpResponseIsOk() throws Exception {
        // Arrange
        String expectedResponse = "Mock response";
        String url = "http://example.com";
        Map<String, String> headers = Collections.singletonMap("Authorization", "Bearer token");

        when(mockConnection.getResponseCode()).thenReturn(HttpURLConnection.HTTP_OK);
        when(mockConnection.getInputStream())
                .thenReturn(new ByteArrayInputStream(expectedResponse.getBytes()));

        // Act
        String actualResponse = httpClient.get(url, headers);

        // Assert
        assertThat(actualResponse).isEqualTo(expectedResponse);
    }

    @Test
    public void get_sendsAllHeadersCorrectly() throws Exception {
        // Arrange
        String url = "http://example.com";
        Map<String, String> headers = new HashMap<>();
        headers.put("Authorization", "Bearer token");
        headers.put("Content-Type", "application/json");

        when(mockConnection.getResponseCode()).thenReturn(HttpURLConnection.HTTP_OK);
        when(mockConnection.getInputStream())
                .thenReturn(new ByteArrayInputStream("Mock response".getBytes()));

        // Act
        httpClient.get(url, headers);

        // Assert
        verify(mockConnection).setRequestProperty("Authorization", "Bearer token");
        verify(mockConnection).setRequestProperty("Content-Type", "application/json");
    }

    @Test
    public void get_throwsIOException_whenHttpResponseIsNotOk() throws Exception {
        // Arrange
        String url = "http://example.com";
        Map<String, String> headers = Collections.emptyMap();

        when(mockConnection.getResponseCode()).thenReturn(HttpURLConnection.HTTP_BAD_REQUEST);

        // Act & Assert
        IOException thrown = assertThrows(IOException.class, () -> httpClient.get(url, headers));
        assertThat(thrown).hasMessageThat().contains("HTTP code 400");
    }

    @Test
    public void get_handlesEmptyResponse() throws Exception {
        // Arrange
        String url = "http://example.com";
        String expectedResponse = "";
        Map<String, String> headers = Collections.emptyMap();

        when(mockConnection.getResponseCode()).thenReturn(HttpURLConnection.HTTP_OK);
        when(mockConnection.getInputStream())
                .thenReturn(new ByteArrayInputStream(expectedResponse.getBytes()));

        // Act
        String actualResponse = httpClient.get(url, headers);

        // Assert
        assertThat(actualResponse).isEqualTo(expectedResponse);
    }

    @Test
    public void get_throwsIOException_whenInputStreamFails() throws Exception {
        // Arrange
        String url = "http://example.com";
        Map<String, String> headers = Collections.emptyMap();

        when(mockConnection.getResponseCode()).thenReturn(HttpURLConnection.HTTP_OK);
        when(mockConnection.getInputStream())
                .thenThrow(new IOException("Stream read error"));

        // Act & Assert
        IOException thrown = assertThrows(IOException.class, () -> httpClient.get(url, headers));
        assertThat(thrown).hasMessageThat().contains("Stream read error");
    }

    @Test
    public void get_throwsIOException_whenCreatingConnectionFails() throws Exception {
        // Arrange
        String url = "http://example.com";
        Map<String, String> headers = Collections.emptyMap();

        when(mockConnectionFactory.create(anyString()))
                .thenThrow(new IOException("Connection failed"));

        // Act & Assert
        IOException thrown = assertThrows(IOException.class, () -> httpClient.get(url, headers));
        assertThat(thrown).hasMessageThat().contains("Connection failed");
    }

    @Test
    public void get_throwsIOException_whenSetRequestMethodFails() throws Exception {
        // Arrange
        String url = "http://example.com";
        Map<String, String> headers = Collections.emptyMap();

        doThrow(new ProtocolException("Invalid method"))
                .when(mockConnection).setRequestMethod("GET");

        // Act & Assert
        IOException thrown = assertThrows(IOException.class, () -> httpClient.get(url, headers));
        assertThat(thrown).hasMessageThat().contains("Invalid method");
    }
}
