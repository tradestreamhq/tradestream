package com.verlumen.tradestream.ingestion;

import static org.mockito.Mockito.verify;

import com.google.inject.testing.fieldbinder.Bind;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import com.google.inject.Guice;
import com.google.inject.Inject;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.mockito.Mock;
import org.mockito.junit.MockitoJUnit;
import org.mockito.junit.MockitoRule;

@RunWith(JUnit4.class)
public class AppTest {
  @Rule public MockitoRule rule = MockitoJUnit.rule();

  @Bind @Mock
  private MarketDataIngestion mockMarketDataIngestion;

  @Inject
  private App app;
  
  @Before
  public void setUp() {
    Guice.createInjector(BoundFieldModule.of(this)).injectMembers(this);
  }
  
  @Test
  public void run_callsMarketDataIngestionStart() {
    // Act
    app.run();
  
    // Assert
    verify(mockMarketDataIngestion).start();
  }

}
